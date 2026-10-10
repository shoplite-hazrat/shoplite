import asyncio
import contextlib
import logging
import time

import nats
import nats.errors
from nats.aio.client import Client
from nats.js import JetStreamContext
from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy
from nats.js.errors import NotFoundError

from .handler import Message, OrderCreatedHandler

log = logging.getLogger(__name__)

ORDERS_STREAM = "ORDERS"  # owned by order-service
SUBJECT = "orders.created"
DURABLE_NAME = "notification-worker"

DLQ_STREAM = "DLQ"  # owned by this worker
DLQ_SUBJECT = f"dlq.{DURABLE_NAME}.{SUBJECT}"


class NatsUnavailable(Exception):
    pass


class JetStreamDeadLetters:
    """Copies failed messages to a separate stream for inspection and replay."""

    def __init__(self, consumer: OrderConsumer) -> None:
        self._consumer = consumer

    async def publish(self, msg: Message, reason: str) -> None:
        await self._consumer.js.publish(
            DLQ_SUBJECT,
            msg.data,
            headers={"Shoplite-Original-Subject": msg.subject, "Shoplite-Error": reason[:500]},
        )


class OrderConsumer:
    """Pulls order.created events from a durable JetStream consumer.

    Durable: the server remembers our position, so restarts and deploys resume
    where they left off. Pull-based: every replica fetches from the same durable
    consumer and JetStream spreads messages across them, so scaling out is just
    adding replicas.
    """

    def __init__(
        self,
        url: str,
        *,
        batch_size: int,
        ack_wait_seconds: int,
        max_deliver: int,
    ) -> None:
        self._url = url
        self._batch_size = batch_size
        self._ack_wait = ack_wait_seconds
        self._max_deliver = max_deliver
        self._nc: Client | None = None
        self._js: JetStreamContext | None = None
        self._sub: JetStreamContext.PullSubscription | None = None
        self._unavailable = False
        # Read by the liveness probe: a stuck loop stops updating this.
        self.last_tick = time.monotonic()

    @property
    def js(self) -> JetStreamContext:
        assert self._js is not None
        return self._js

    @property
    def ready(self) -> bool:
        return self._sub is not None and self._nc is not None and self._nc.is_connected

    async def _connect(self) -> None:
        if self._nc is None:
            try:
                # Bounded: nats-py retries the initial connect forever otherwise.
                self._nc = await asyncio.wait_for(
                    nats.connect(
                        self._url,
                        name=DURABLE_NAME,
                        connect_timeout=2,
                        max_reconnect_attempts=-1,
                        error_cb=self._on_error,
                        disconnected_cb=self._on_disconnected,
                        reconnected_cb=self._on_reconnected,
                    ),
                    timeout=3,
                )
            except (TimeoutError, OSError, nats.errors.Error) as exc:
                raise NatsUnavailable(f"cannot connect to {self._url}") from exc
            self._js = self._nc.jetstream()
            log.info("connected to NATS", extra={"url": self._url})

        if not self._nc.is_connected:
            raise NatsUnavailable("NATS connection is down; client is reconnecting")

        if self._sub is None:
            await self._ensure_dlq_stream()
            try:
                self._sub = await self.js.pull_subscribe(
                    SUBJECT,
                    durable=DURABLE_NAME,
                    stream=ORDERS_STREAM,
                    config=ConsumerConfig(
                        ack_policy=AckPolicy.EXPLICIT,
                        ack_wait=self._ack_wait,
                        # +1 so our handler sees the final attempt and can
                        # dead-letter it before JetStream stops redelivering.
                        max_deliver=self._max_deliver + 1,
                        deliver_policy=DeliverPolicy.ALL,
                        max_ack_pending=1000,
                    ),
                )
            except NotFoundError as exc:
                # order-service creates the stream; it may not have started yet.
                raise NatsUnavailable(f"stream {ORDERS_STREAM} does not exist yet") from exc
            log.info("subscribed", extra={"stream": ORDERS_STREAM, "durable": DURABLE_NAME})

    async def _ensure_dlq_stream(self) -> None:
        try:
            await self.js.stream_info(DLQ_STREAM)
        except NotFoundError:
            await self.js.add_stream(name=DLQ_STREAM, subjects=["dlq.>"])
            log.info("created JetStream stream", extra={"stream": DLQ_STREAM})

    async def _on_error(self, exc: Exception) -> None:
        log.warning("NATS client error", extra={"error": f"{type(exc).__name__}: {exc}"})

    async def _on_disconnected(self) -> None:
        log.warning("disconnected from NATS")

    async def _on_reconnected(self) -> None:
        # The server may have restarted without its data; re-create the
        # consumer (and DLQ stream) on the next tick.
        self._sub = None
        log.info("reconnected to NATS")

    async def run(self, handler: OrderCreatedHandler, stop: asyncio.Event) -> None:
        log.info("consumer started")
        while not stop.is_set():
            self.last_tick = time.monotonic()
            try:
                await self._connect()
                if self._unavailable:
                    self._unavailable = False
                    log.info("NATS available again; consuming")
                assert self._sub is not None
                # Short timeout: the loop must tick regularly for liveness and
                # to notice shutdown.
                messages = await self._sub.fetch(self._batch_size, timeout=5)
            except nats.errors.TimeoutError:
                continue  # no messages right now
            except NatsUnavailable as exc:
                if not self._unavailable:
                    self._unavailable = True
                    log.warning("cannot consume yet; retrying", extra={"error": str(exc)})
                await self._sleep(stop, 2)
                continue
            except Exception:
                log.warning("fetch failed; retrying", exc_info=True)
                self._sub = None
                await self._sleep(stop, 2)
                continue

            # Finish the whole batch even if shutdown was requested: each
            # message is short, and unfinished ones would wait for ack_wait.
            for msg in messages:
                await handler.handle(msg)
        log.info("consumer stopped")

    @staticmethod
    async def _sleep(stop: asyncio.Event, seconds: float) -> None:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=seconds)

    async def close(self) -> None:
        if self._nc is not None and not self._nc.is_closed:
            # Not drain(): with a pull subscription there is nothing to drain and
            # nats-py waits out its full drain timeout. Flush pending acks, then close.
            with contextlib.suppress(Exception):
                await self._nc.flush(timeout=2)
            await self._nc.close()

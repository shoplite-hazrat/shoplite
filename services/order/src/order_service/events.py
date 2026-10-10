import asyncio
import logging

import nats
import nats.errors
from nats.aio.client import Client
from nats.js import JetStreamContext
from nats.js.errors import NotFoundError

log = logging.getLogger(__name__)

STREAM_NAME = "ORDERS"
STREAM_SUBJECTS = ["orders.>"]


class NatsUnavailable(Exception):
    pass


class NatsPublisher:
    """Publishes to NATS JetStream (persistent, at-least-once delivery).

    Connects lazily so the service starts and takes orders even while NATS is
    down; the outbox holds events until the connection is back.
    """

    def __init__(self, url: str, *, connect_timeout: float = 3.0) -> None:
        self._url = url
        self._connect_timeout = connect_timeout
        self._nc: Client | None = None
        self._js: JetStreamContext | None = None
        self._stream_ready = False

    async def ensure_connected(self) -> None:
        """Raise NatsUnavailable quickly instead of blocking the caller.

        After the first successful connect the client reconnects by itself in
        the background; until it does, callers fail fast and retry later.
        """
        if self._nc is None:
            try:
                # nats-py retries the *initial* connect forever with
                # max_reconnect_attempts=-1, so bound it ourselves.
                self._nc = await asyncio.wait_for(
                    nats.connect(
                        self._url,
                        name="order-service",
                        connect_timeout=2,
                        max_reconnect_attempts=-1,
                        error_cb=self._on_error,
                        disconnected_cb=self._on_disconnected,
                        reconnected_cb=self._on_reconnected,
                    ),
                    timeout=self._connect_timeout,
                )
            except (TimeoutError, OSError, nats.errors.Error) as exc:
                raise NatsUnavailable(f"cannot connect to {self._url}") from exc
            self._js = self._nc.jetstream()
            log.info("connected to NATS", extra={"url": self._url})

        if not self._nc.is_connected:
            raise NatsUnavailable("NATS connection is down; client is reconnecting")
        if not self._stream_ready:
            await self._ensure_stream()
            self._stream_ready = True

    async def _on_error(self, exc: Exception) -> None:
        log.warning("NATS client error", extra={"error": f"{type(exc).__name__}: {exc}"})

    async def _on_disconnected(self) -> None:
        log.warning("disconnected from NATS")

    async def _on_reconnected(self) -> None:
        # The server may have restarted without its data; re-check the stream.
        self._stream_ready = False
        log.info("reconnected to NATS")

    async def _ensure_stream(self) -> None:
        assert self._js is not None
        try:
            await self._js.stream_info(STREAM_NAME)
        except NotFoundError:
            await self._js.add_stream(name=STREAM_NAME, subjects=STREAM_SUBJECTS)
            log.info("created JetStream stream", extra={"stream": STREAM_NAME})

    async def publish(self, subject: str, payload: bytes, msg_id: str) -> None:
        assert self._js is not None
        # Nats-Msg-Id lets JetStream drop duplicates if the relay re-sends.
        await self._js.publish(subject, payload, headers={"Nats-Msg-Id": msg_id})

    async def close(self) -> None:
        if self._nc is not None and not self._nc.is_closed:
            await self._nc.drain()

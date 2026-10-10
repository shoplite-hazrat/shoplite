import asyncio
import contextlib
import json
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .events import NatsPublisher, NatsUnavailable
from .metrics import EVENTS_PUBLISHED, OUTBOX_PENDING
from .models import OutboxEvent, utcnow

log = logging.getLogger(__name__)


class OutboxRelay:
    """Moves events from the outbox table to NATS.

    Delivery is at-least-once: if publishing fails part-way through a batch, the
    transaction rolls back and the batch is sent again. JetStream deduplicates
    by message id, and consumers must be idempotent anyway.

    FOR UPDATE SKIP LOCKED lets several replicas run relays concurrently without
    sending the same row twice at the same time.
    """

    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        publisher: NatsPublisher,
        *,
        poll_interval: float,
        batch_size: int,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._publisher = publisher
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._nats_down = False

    async def run_once(self) -> int:
        async with self._sessionmaker() as session, session.begin():
            result = await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.created_at)
                .limit(self._batch_size)
                .with_for_update(skip_locked=True)
            )
            events = list(result.scalars())
            for event in events:
                await self._publisher.publish(
                    event.subject, json.dumps(event.payload).encode(), str(event.id)
                )
                event.published_at = utcnow()
        EVENTS_PUBLISHED.inc(len(events))
        return len(events)

    async def refresh_pending_gauge(self) -> None:
        # Measured separately from publishing so the gauge keeps rising while
        # NATS is down, which is exactly when the alert needs to fire.
        async with self._sessionmaker() as session:
            pending = await session.scalar(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
            )
        OUTBOX_PENDING.set(pending or 0)

    async def run(self, stop: asyncio.Event) -> None:
        log.info("outbox relay started")
        while not stop.is_set():
            published = 0
            try:
                await self._publisher.ensure_connected()
                if self._nats_down:
                    self._nats_down = False
                    log.info("NATS available again; resuming outbox delivery")
                published = await self.run_once()
            except NatsUnavailable as exc:
                # Log the transition once, not every tick; the gauge tracks the backlog.
                if not self._nats_down:
                    self._nats_down = True
                    log.warning(
                        "NATS unavailable; buffering events in outbox", extra={"error": str(exc)}
                    )
            except Exception:
                log.warning("outbox relay iteration failed; will retry", exc_info=True)
            try:
                await self.refresh_pending_gauge()
            except Exception:
                log.warning("could not count pending outbox events", exc_info=True)

            if published == self._batch_size:
                continue  # more waiting; drain without sleeping
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=self._poll_interval)
        log.info("outbox relay stopped")

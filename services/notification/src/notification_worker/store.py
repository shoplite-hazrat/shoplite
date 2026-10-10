from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class ProcessedEventStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def ping(self) -> None:
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    @asynccontextmanager
    async def claim(self, event_id: str, order_id: str, recipient: str) -> AsyncIterator[bool]:
        """Yield True if this event has not been processed yet.

        The insert and the work inside the block share one transaction: if the
        block raises (e.g. SMTP fails) the claim is rolled back and the event
        can be retried. If another replica is handling the same event right now,
        the insert waits on the primary key until that transaction finishes.
        """
        async with self._engine.begin() as conn:
            result = await conn.execute(
                text(
                    "INSERT INTO processed_events (event_id, order_id, recipient) "
                    "VALUES (:event_id, :order_id, :recipient) ON CONFLICT DO NOTHING"
                ),
                {"event_id": event_id, "order_id": order_id, "recipient": recipient},
            )
            yield result.rowcount == 1

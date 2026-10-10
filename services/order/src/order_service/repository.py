import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models import Order, OutboxEvent


class OrderRepository:
    """Postgres access for orders. Tests use an in-memory fake with the same methods."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def ping(self) -> None:
        async with self._sessionmaker() as session:
            await session.execute(text("SELECT 1"))

    async def save_with_event(self, order: Order, event: OutboxEvent) -> None:
        # One transaction: either the order and its event both exist, or neither does.
        async with self._sessionmaker() as session, session.begin():
            session.add_all([order, event])

    async def get(self, order_id: uuid.UUID) -> Order | None:
        async with self._sessionmaker() as session:
            return await session.get(Order, order_id)

    async def list(self, limit: int, offset: int) -> list[Order]:
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(Order).order_by(Order.created_at.desc()).limit(limit).offset(offset)
            )
            return list(result.scalars())

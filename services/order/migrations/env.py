import asyncio
import logging
import os

from alembic import context
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from order_service.config import normalize_db_url
from order_service.models import Base

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
target_metadata = Base.metadata

# Arbitrary constant: all migrators for this database share one advisory lock.
MIGRATION_LOCK_ID = 727_001


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        # If two migration Jobs ever run at once, the second waits here.
        connection.execute(text(f"SELECT pg_advisory_xact_lock({MIGRATION_LOCK_ID})"))
        context.run_migrations()


async def _run_online() -> None:
    engine = create_async_engine(normalize_db_url(os.environ["DATABASE_URL"]))
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=normalize_db_url(os.environ["DATABASE_URL"]),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(_run_online())

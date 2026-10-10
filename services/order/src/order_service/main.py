import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .api import build_app
from .catalog_client import CatalogClient
from .config import Settings
from .events import NatsPublisher
from .logging_setup import configure_logging
from .outbox import OutboxRelay
from .repository import OrderRepository
from .service import OrderService

settings = Settings()
configure_logging(settings.log_level)
log = logging.getLogger("order_service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_async_engine(
        settings.database_url, pool_size=settings.db_pool_size, pool_pre_ping=True
    )
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    repo = OrderRepository(sessionmaker)
    catalog = CatalogClient(
        settings.catalog_url,
        timeout_seconds=settings.catalog_timeout_seconds,
        retries=settings.catalog_retries,
    )
    publisher = NatsPublisher(settings.nats_url)
    relay = OutboxRelay(
        sessionmaker,
        publisher,
        poll_interval=settings.outbox_poll_interval_seconds,
        batch_size=settings.outbox_batch_size,
    )

    app.state.repo = repo
    app.state.order_service = OrderService(repo, catalog)
    stop = asyncio.Event()
    relay_task = asyncio.create_task(relay.run(stop))
    log.info("order-service started")

    yield

    # Uvicorn has already stopped accepting connections and drained in-flight
    # requests by now; stop background work and close connections.
    app.state.shutting_down = True
    stop.set()
    await relay_task
    await catalog.aclose()
    await publisher.close()
    await engine.dispose()
    log.info("order-service stopped")


app = build_app(lifespan=lifespan)

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from .api import build_app
from .config import Settings
from .consumer import JetStreamDeadLetters, OrderConsumer
from .handler import OrderCreatedHandler
from .logging_setup import configure_logging
from .mailer import Mailer
from .store import ProcessedEventStore

settings = Settings()
configure_logging(settings.log_level)
log = logging.getLogger("notification_worker")


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_async_engine(settings.database_url, pool_size=2, pool_pre_ping=True)
    store = ProcessedEventStore(engine)
    mailer = Mailer(
        settings.smtp_host, settings.smtp_port, settings.mail_from, settings.smtp_timeout_seconds
    )
    consumer = OrderConsumer(
        settings.nats_url,
        batch_size=settings.batch_size,
        ack_wait_seconds=settings.ack_wait_seconds,
        max_deliver=settings.max_deliver,
    )
    handler = OrderCreatedHandler(
        store, mailer, JetStreamDeadLetters(consumer), max_deliver=settings.max_deliver
    )

    app.state.store = store
    app.state.consumer = consumer
    stop = asyncio.Event()
    task = asyncio.create_task(consumer.run(handler, stop))
    if not settings.smtp_host:
        log.warning("SMTP_HOST not set: emails will only be logged (dry-run)")
    log.info("notification-worker started")

    yield

    app.state.shutting_down = True
    stop.set()
    await task  # finishes the in-flight batch
    await consumer.close()
    await engine.dispose()
    log.info("notification-worker stopped")


app = build_app(lifespan=lifespan, liveness_stale_seconds=settings.liveness_stale_seconds)

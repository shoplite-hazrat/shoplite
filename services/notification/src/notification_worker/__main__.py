import uvicorn

from .main import settings

uvicorn.run(
    "notification_worker.main:app",
    host=settings.host,
    port=settings.port,
    # Logging is configured by the app (JSON); don't let uvicorn override it.
    log_config=None,
    timeout_graceful_shutdown=10,
)

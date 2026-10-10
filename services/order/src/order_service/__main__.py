import uvicorn

from .main import settings

uvicorn.run(
    "order_service.main:app",
    host=settings.host,
    port=settings.port,
    # Logging is configured by the app (JSON); don't let uvicorn override it.
    log_config=None,
    # On SIGTERM, wait this long for in-flight requests before closing.
    timeout_graceful_shutdown=settings.shutdown_timeout_seconds,
    proxy_headers=True,
)

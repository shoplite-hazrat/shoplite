import logging
import sys
from contextvars import ContextVar

from pythonjsonlogger.json import JsonFormatter

# Set per request by the HTTP middleware; read by the log filter and by the
# catalog client so the id follows the request to the next service.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: str) -> None:
    """JSON logs to stdout; the platform (Loki, etc.) collects them from there."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter(
            "{levelname}{name}{message}",
            style="{",
            timestamp="time",  # ISO-8601 UTC
            rename_fields={"levelname": "level"},
        )
    )
    handler.addFilter(_RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
    # The middleware writes one structured line per request instead.
    logging.getLogger("uvicorn.access").disabled = True
    # httpx logs every outgoing call at INFO; failures are logged by our client.
    logging.getLogger("httpx").setLevel(logging.WARNING)

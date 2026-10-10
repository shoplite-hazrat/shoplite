import logging
import sys

from pythonjsonlogger.json import JsonFormatter


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

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
    # Probes and scrapes hit this server constantly; don't log each one.
    logging.getLogger("uvicorn.access").disabled = True

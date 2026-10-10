from pydantic import field_validator
from pydantic_settings import BaseSettings


def normalize_db_url(url: str) -> str:
    """Accept the usual postgres:// form and select the asyncpg driver."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url.removeprefix(prefix)
    return url


class Settings(BaseSettings):
    """All configuration comes from environment variables (12-factor)."""

    database_url: str
    nats_url: str = "nats://nats:4222"

    # Unset SMTP_HOST = dry-run: emails are logged instead of sent.
    smtp_host: str | None = None
    smtp_port: int = 1025
    smtp_timeout_seconds: float = 10.0
    mail_from: str = "ShopLite <orders@shoplite.local>"

    # Health and metrics only; the worker serves no business API.
    host: str = "0.0.0.0"
    port: int = 8001
    log_level: str = "INFO"

    batch_size: int = 10
    # Redeliver if not acked within this time (worker crashed or hung).
    ack_wait_seconds: int = 30
    # After this many failed deliveries the message goes to the dead-letter queue.
    max_deliver: int = 5
    # Liveness fails if the consume loop hasn't ticked for this long.
    liveness_stale_seconds: int = 60

    @field_validator("database_url")
    @classmethod
    def _normalize(cls, v: str) -> str:
        return normalize_db_url(v)

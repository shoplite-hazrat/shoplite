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
    catalog_url: str = "http://catalog:3000"
    nats_url: str = "nats://nats:4222"

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    db_pool_size: int = 5
    # Keep below the pod's terminationGracePeriodSeconds.
    shutdown_timeout_seconds: int = 10

    catalog_timeout_seconds: float = 2.0
    catalog_retries: int = 2

    outbox_poll_interval_seconds: float = 1.0
    outbox_batch_size: int = 100

    @field_validator("database_url")
    @classmethod
    def _normalize(cls, v: str) -> str:
        return normalize_db_url(v)

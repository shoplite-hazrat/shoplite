from datetime import datetime

from sqlalchemy import DateTime, Text, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProcessedEvent(Base):
    """Idempotency record ("inbox"): one row per event that produced an email.

    The event id primary key is what turns at-least-once delivery into
    effectively-once emails.
    """

    __tablename__ = "processed_events"

    event_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    order_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    recipient: Mapped[str] = mapped_column(Text)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

import json
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from notification_worker.handler import OrderCreatedHandler

MAX_DELIVER = 3


class FakeMsg:
    def __init__(self, data: bytes, attempt: int = 1, subject: str = "orders.created") -> None:
        self.subject = subject
        self.data = data
        self.headers = None
        self.metadata = SimpleNamespace(num_delivered=attempt)
        self.outcome: str | None = None
        self.nak_delay: float | None = None

    async def ack(self):
        self.outcome = "ack"

    async def nak(self, delay=None):
        self.outcome = "nak"
        self.nak_delay = delay

    async def term(self):
        self.outcome = "term"


class FakeStore:
    """Same contract as ProcessedEventStore: the claim rolls back if the block raises."""

    def __init__(self) -> None:
        self.processed: set[str] = set()
        self.healthy = True

    async def ping(self):
        if not self.healthy:
            raise ConnectionError("database down")

    @asynccontextmanager
    async def claim(self, event_id, order_id, recipient):
        if event_id in self.processed:
            yield False
            return
        yield True
        self.processed.add(event_id)  # only reached if the block didn't raise


class FakeMailer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self.failing = False

    async def send(self, to, subject, body):
        if self.failing:
            raise ConnectionRefusedError("smtp down")
        self.sent.append((to, subject, body))


class FakeDeadLetters:
    def __init__(self) -> None:
        self.messages: list[tuple[FakeMsg, str]] = []

    async def publish(self, msg, reason):
        self.messages.append((msg, reason))


def order_created_event(event_id: str | None = None) -> bytes:
    return json.dumps(
        {
            "id": event_id or str(uuid.uuid4()),
            "type": "order.created",
            "occurredAt": "2026-10-10T09:00:00+00:00",
            "data": {
                "orderId": str(uuid.uuid4()),
                "customerEmail": "ada@example.com",
                "totalCents": 4497,
                "items": [
                    {
                        "productId": str(uuid.uuid4()),
                        "name": "Mug",
                        "quantity": 2,
                        "unitPriceCents": 999,
                    },
                    {
                        "productId": str(uuid.uuid4()),
                        "name": "Cap",
                        "quantity": 1,
                        "unitPriceCents": 2499,
                    },
                ],
            },
        }
    ).encode()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def store():
    return FakeStore()


@pytest.fixture
def mailer():
    return FakeMailer()


@pytest.fixture
def dead_letters():
    return FakeDeadLetters()


@pytest.fixture
def handler(store, mailer, dead_letters):
    return OrderCreatedHandler(store, mailer, dead_letters, max_deliver=MAX_DELIVER)

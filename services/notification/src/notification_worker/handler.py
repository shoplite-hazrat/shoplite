import json
import logging
import time
from typing import Any, Protocol

from .metrics import EVENTS_PROCESSED, PROCESSING_DURATION

log = logging.getLogger(__name__)

MAX_RETRY_DELAY_SECONDS = 60


class Message(Protocol):
    """The parts of a JetStream message the handler uses (nats.aio.msg.Msg)."""

    subject: str
    data: bytes
    headers: dict[str, str] | None

    @property
    def metadata(self) -> Any: ...
    async def ack(self) -> None: ...
    async def nak(self, delay: float | None = None) -> None: ...
    async def term(self) -> None: ...


class Store(Protocol):
    def claim(self, event_id: str, order_id: str, recipient: str) -> Any: ...


class Mail(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


class DeadLetters(Protocol):
    async def publish(self, msg: Message, reason: str) -> None: ...


class PoisonMessage(Exception):
    """The message can never be processed, so retrying is pointless."""


def parse_order_created(data: bytes) -> dict[str, Any]:
    try:
        event = json.loads(data)
        order = event["data"]
        return {
            "event_id": event["id"],
            "order_id": order["orderId"],
            "email": order["customerEmail"],
            "total_cents": int(order["totalCents"]),
            "items": [
                (item["name"], int(item["quantity"]), int(item["unitPriceCents"]))
                for item in order["items"]
            ],
        }
    except (ValueError, KeyError, TypeError) as exc:
        raise PoisonMessage(f"malformed order.created event: {exc!r}") from exc


def render_email(order: dict[str, Any]) -> tuple[str, str]:
    lines = [f"  {qty} x {name} @ ${price / 100:.2f}" for name, qty, price in order["items"]]
    subject = f"Your ShopLite order {order['order_id'][:8]} is confirmed"
    body = "\n".join(
        [
            "Thanks for your order!",
            "",
            *lines,
            "",
            f"Total: ${order['total_cents'] / 100:.2f}",
            f"Order id: {order['order_id']}",
        ]
    )
    return subject, body


class OrderCreatedHandler:
    """Turns one order.created message into one confirmation email.

    Outcomes:
      sent / duplicate  -> ack
      transient failure -> nak with exponential delay (JetStream redelivers)
      last attempt      -> copy to the dead-letter queue, then term
      poison message    -> dead-letter immediately, then term
    """

    def __init__(
        self, store: Store, mailer: Mail, dead_letters: DeadLetters, *, max_deliver: int
    ) -> None:
        self._store = store
        self._mailer = mailer
        self._dead_letters = dead_letters
        self._max_deliver = max_deliver

    async def handle(self, msg: Message) -> None:
        start = time.perf_counter()
        attempt = msg.metadata.num_delivered
        try:
            result = await self._process(msg)
            await msg.ack()
        except PoisonMessage as exc:
            log.error("poison message", extra={"subject": msg.subject, "error": str(exc)})
            await self._dead_letters.publish(msg, str(exc))
            await msg.term()
            result = "poison"
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            if attempt >= self._max_deliver:
                log.error(
                    "giving up on event; sending to dead-letter queue",
                    extra={"attempt": attempt, "error": reason},
                )
                await self._dead_letters.publish(msg, reason)
                await msg.term()
                result = "dead_lettered"
            else:
                delay = min(2**attempt, MAX_RETRY_DELAY_SECONDS)
                log.warning(
                    "event processing failed; will retry",
                    extra={"attempt": attempt, "retry_in_s": delay, "error": reason},
                )
                await msg.nak(delay=delay)
                result = "retry"
        EVENTS_PROCESSED.labels(result).inc()
        PROCESSING_DURATION.observe(time.perf_counter() - start)

    async def _process(self, msg: Message) -> str:
        order = parse_order_created(msg.data)
        async with self._store.claim(order["event_id"], order["order_id"], order["email"]) as new:
            if not new:
                log.info("duplicate event skipped", extra={"event_id": order["event_id"]})
                return "duplicate"
            subject, body = render_email(order)
            # Sent inside the claim's transaction: if sending fails, the claim
            # rolls back and a retry can send it. If the commit fails after a
            # successful send, the customer may get a second email; that is the
            # accepted cost of at-least-once delivery.
            await self._mailer.send(order["email"], subject, body)
        log.info(
            "confirmation email sent",
            extra={"event_id": order["event_id"], "order_id": order["order_id"]},
        )
        return "sent"

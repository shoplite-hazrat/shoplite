import logging
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from .catalog_client import CatalogError, Product
from .metrics import ORDERS_CREATED
from .models import Order, OrderItem, OutboxEvent, utcnow

log = logging.getLogger(__name__)

ORDER_CREATED_SUBJECT = "orders.created"


@dataclass(frozen=True)
class OrderLine:
    product_id: uuid.UUID
    quantity: int


class Catalog(Protocol):
    async def get_product(self, product_id: uuid.UUID) -> Product: ...
    async def reserve(self, product_id: uuid.UUID, order_id: uuid.UUID, quantity: int) -> None: ...
    async def release(self, product_id: uuid.UUID, order_id: uuid.UUID) -> None: ...


class Repository(Protocol):
    async def save_with_event(self, order: Order, event: OutboxEvent) -> None: ...


class OrderService:
    def __init__(self, repo: Repository, catalog: Catalog) -> None:
        self._repo = repo
        self._catalog = catalog

    async def place_order(self, customer_email: str, lines: list[OrderLine]) -> Order:
        """Saga: reserve stock for every line, then persist the order and its event.

        If any step fails, already-attempted reservations are released (the
        compensating action) and the error propagates to the caller.
        """
        quantities = Counter[uuid.UUID]()
        for line in lines:
            quantities[line.product_id] += line.quantity

        order_id = uuid.uuid4()
        products = {pid: await self._catalog.get_product(pid) for pid in quantities}

        attempted: list[uuid.UUID] = []
        try:
            for pid, quantity in quantities.items():
                # Track before calling: a timeout may hide a reservation that succeeded.
                attempted.append(pid)
                await self._catalog.reserve(pid, order_id, quantity)

            order = Order(
                id=order_id,
                customer_email=customer_email,
                status="confirmed",
                total_cents=sum(products[pid].price_cents * q for pid, q in quantities.items()),
                created_at=utcnow(),
                items=[
                    OrderItem(
                        order_id=order_id,
                        product_id=pid,
                        product_name=products[pid].name,
                        unit_price_cents=products[pid].price_cents,
                        quantity=q,
                    )
                    for pid, q in quantities.items()
                ],
            )
            await self._repo.save_with_event(order, _order_created_event(order))
        except BaseException:
            await self._compensate(order_id, attempted)
            raise

        ORDERS_CREATED.inc()
        log.info(
            "order placed", extra={"order_id": str(order_id), "total_cents": order.total_cents}
        )
        return order

    async def _compensate(self, order_id: uuid.UUID, product_ids: list[uuid.UUID]) -> None:
        for pid in product_ids:
            try:
                await self._catalog.release(pid, order_id)
            except CatalogError:
                # Stock stays reserved until a reconciliation job cleans it up.
                # Alert on this log line / metric in production.
                log.error(
                    "failed to release reservation",
                    extra={"order_id": str(order_id), "product_id": str(pid)},
                )


def _order_created_event(order: Order) -> OutboxEvent:
    event_id = uuid.uuid4()
    return OutboxEvent(
        id=event_id,
        subject=ORDER_CREATED_SUBJECT,
        created_at=utcnow(),
        payload={
            "id": str(event_id),
            "type": "order.created",
            "occurredAt": order.created_at.isoformat(),
            "data": {
                "orderId": str(order.id),
                "customerEmail": order.customer_email,
                "totalCents": order.total_cents,
                "items": [
                    {
                        "productId": str(item.product_id),
                        "name": item.product_name,
                        "quantity": item.quantity,
                        "unitPriceCents": item.unit_price_cents,
                    }
                    for item in order.items
                ],
            },
        },
    )

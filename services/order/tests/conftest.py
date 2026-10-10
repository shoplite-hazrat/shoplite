import uuid

import httpx
import pytest

from order_service.api import build_app
from order_service.catalog_client import (
    CatalogUnavailable,
    InsufficientStock,
    Product,
    ProductNotFound,
)
from order_service.service import OrderService


class FakeCatalog:
    """Behaves like catalog-service: idempotent reserve/release per order."""

    def __init__(self) -> None:
        self.products: dict[uuid.UUID, Product] = {}
        self.stock: dict[uuid.UUID, int] = {}
        self.reservations: dict[tuple[uuid.UUID, uuid.UUID], int] = {}
        self.unavailable_on_reserve: set[uuid.UUID] = set()

    def add(self, name: str, price_cents: int, stock: int) -> uuid.UUID:
        pid = uuid.uuid4()
        self.products[pid] = Product(id=pid, name=name, price_cents=price_cents)
        self.stock[pid] = stock
        return pid

    async def get_product(self, product_id):
        if product_id not in self.products:
            raise ProductNotFound(product_id)
        return self.products[product_id]

    async def reserve(self, product_id, order_id, quantity):
        if product_id in self.unavailable_on_reserve:
            raise CatalogUnavailable("simulated outage")
        if (order_id, product_id) in self.reservations:
            return
        if self.stock[product_id] < quantity:
            raise InsufficientStock(product_id)
        self.stock[product_id] -= quantity
        self.reservations[(order_id, product_id)] = quantity

    async def release(self, product_id, order_id):
        quantity = self.reservations.pop((order_id, product_id), None)
        if quantity is not None:
            self.stock[product_id] += quantity


class FakeRepository:
    def __init__(self) -> None:
        self.orders: dict = {}
        self.events: list = []
        self.healthy = True
        self.fail_save = False

    async def ping(self):
        if not self.healthy:
            raise ConnectionError("database down")

    async def save_with_event(self, order, event):
        if self.fail_save:
            raise ConnectionError("database down")
        self.orders[order.id] = order
        self.events.append(event)

    async def get(self, order_id):
        return self.orders.get(order_id)

    async def list(self, limit, offset):
        ordered = sorted(self.orders.values(), key=lambda o: o.created_at, reverse=True)
        return ordered[offset : offset + limit]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def catalog():
    return FakeCatalog()


@pytest.fixture
def repo():
    return FakeRepository()


@pytest.fixture
def app(repo, catalog):
    app = build_app()
    app.state.repo = repo
    app.state.order_service = OrderService(repo, catalog)
    return app


@pytest.fixture
async def client(app):
    # raise_app_exceptions=False: unhandled errors become 500s, as in production.
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

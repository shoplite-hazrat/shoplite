import uuid

import httpx
import pytest

from order_service.catalog_client import (
    CatalogClient,
    CatalogUnavailable,
    InsufficientStock,
    ProductNotFound,
)
from order_service.logging_setup import request_id_var

pytestmark = pytest.mark.anyio

PID = uuid.uuid4()
OID = uuid.uuid4()


def client_with(handler, retries=2):
    return CatalogClient(
        "http://catalog", timeout_seconds=1, retries=retries, transport=httpx.MockTransport(handler)
    )


async def test_retries_server_errors_then_succeeds():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"id": str(PID), "name": "Mug", "priceCents": 1299})

    product = await client_with(handler).get_product(PID)
    assert product.price_cents == 1299
    assert len(calls) == 3


async def test_gives_up_after_retries():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ConnectError("refused")

    with pytest.raises(CatalogUnavailable):
        await client_with(handler, retries=1).reserve(PID, OID, 1)
    assert len(calls) == 2


async def test_does_not_retry_client_errors():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(409)

    with pytest.raises(InsufficientStock):
        await client_with(handler).reserve(PID, OID, 1)
    assert len(calls) == 1


async def test_maps_404_to_product_not_found():
    with pytest.raises(ProductNotFound):
        await client_with(lambda r: httpx.Response(404)).get_product(PID)


async def test_propagates_request_id():
    seen = {}

    def handler(request):
        seen["id"] = request.headers.get("x-request-id")
        return httpx.Response(200, json={})

    token = request_id_var.set("req-42")
    try:
        await client_with(handler).release(PID, OID)
    finally:
        request_id_var.reset(token)
    assert seen["id"] == "req-42"

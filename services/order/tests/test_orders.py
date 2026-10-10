import uuid

import pytest

pytestmark = pytest.mark.anyio


def order_body(*items, email="ada@example.com"):
    return {
        "customerEmail": email,
        "items": [{"productId": str(pid), "quantity": q} for pid, q in items],
    }


async def test_places_order_reserves_stock_and_records_event(client, catalog, repo):
    mug = catalog.add("Mug", 1299, stock=5)
    cap = catalog.add("Cap", 2499, stock=2)

    res = await client.post("/v1/orders", json=order_body((mug, 2), (cap, 1)))

    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "confirmed"
    assert body["totalCents"] == 2 * 1299 + 2499
    assert res.headers["location"] == f"/v1/orders/{body['id']}"
    assert catalog.stock == {mug: 3, cap: 1}

    [event] = repo.events
    assert event.subject == "orders.created"
    assert event.payload["type"] == "order.created"
    assert event.payload["data"]["orderId"] == body["id"]
    assert event.payload["data"]["totalCents"] == body["totalCents"]


async def test_merges_duplicate_lines(client, catalog):
    mug = catalog.add("Mug", 1000, stock=5)
    res = await client.post("/v1/orders", json=order_body((mug, 1), (mug, 2)))
    assert res.status_code == 201
    assert res.json()["items"] == [
        {"productId": str(mug), "productName": "Mug", "unitPriceCents": 1000, "quantity": 3}
    ]


async def test_unknown_product_is_rejected_without_reserving(client, catalog, repo):
    mug = catalog.add("Mug", 1000, stock=5)
    res = await client.post("/v1/orders", json=order_body((mug, 1), (uuid.uuid4(), 1)))
    assert res.status_code == 422
    assert catalog.stock[mug] == 5
    assert repo.orders == {}


async def test_insufficient_stock_releases_earlier_reservations(client, catalog, repo):
    mug = catalog.add("Mug", 1000, stock=5)
    cap = catalog.add("Cap", 2000, stock=1)
    res = await client.post("/v1/orders", json=order_body((mug, 2), (cap, 3)))
    assert res.status_code == 409
    assert catalog.stock == {mug: 5, cap: 1}  # compensated
    assert catalog.reservations == {}
    assert repo.orders == {}
    assert repo.events == []


async def test_catalog_outage_returns_503_and_compensates(client, catalog):
    mug = catalog.add("Mug", 1000, stock=5)
    cap = catalog.add("Cap", 2000, stock=5)
    catalog.unavailable_on_reserve.add(cap)
    res = await client.post("/v1/orders", json=order_body((mug, 1), (cap, 1)))
    assert res.status_code == 503
    assert res.headers["retry-after"] == "2"
    assert catalog.stock[mug] == 5


async def test_database_failure_releases_reservations(client, catalog, repo):
    mug = catalog.add("Mug", 1000, stock=5)
    repo.fail_save = True
    res = await client.post("/v1/orders", json=order_body((mug, 2)))
    assert res.status_code == 500
    assert catalog.stock[mug] == 5


@pytest.mark.parametrize(
    "body",
    [
        {"customerEmail": "ada@example.com", "items": []},
        {
            "customerEmail": "not-an-email",
            "items": [{"productId": str(uuid.uuid4()), "quantity": 1}],
        },
        {"customerEmail": "ada@example.com", "items": [{"productId": "nope", "quantity": 1}]},
        {
            "customerEmail": "ada@example.com",
            "items": [{"productId": str(uuid.uuid4()), "quantity": 0}],
        },
    ],
)
async def test_rejects_invalid_input(client, body):
    res = await client.post("/v1/orders", json=body)
    assert res.status_code == 422


async def test_get_and_list_orders(client, catalog):
    mug = catalog.add("Mug", 1000, stock=5)
    created = (await client.post("/v1/orders", json=order_body((mug, 1)))).json()

    got = await client.get(f"/v1/orders/{created['id']}")
    assert got.status_code == 200
    assert got.json() == created

    listed = await client.get("/v1/orders?limit=10")
    assert [o["id"] for o in listed.json()["items"]] == [created["id"]]

    missing = await client.get(f"/v1/orders/{uuid.uuid4()}")
    assert missing.status_code == 404

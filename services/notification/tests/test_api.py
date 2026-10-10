import time
from types import SimpleNamespace

import httpx
import pytest

from notification_worker.api import build_app

pytestmark = pytest.mark.anyio


@pytest.fixture
def consumer():
    return SimpleNamespace(last_tick=time.monotonic(), ready=True)


@pytest.fixture
async def client(store, consumer):
    app = build_app(liveness_stale_seconds=60)
    app.state.store = store
    app.state.consumer = consumer
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        c.app = app
        yield c


async def test_liveness_ok_while_loop_ticks(client):
    assert (await client.get("/healthz")).status_code == 200


async def test_liveness_fails_when_loop_is_stuck(client, consumer):
    consumer.last_tick = time.monotonic() - 120
    res = await client.get("/healthz")
    assert res.status_code == 503
    assert res.json()["status"] == "stuck"


async def test_readiness_requires_nats_and_database(client, consumer, store):
    assert (await client.get("/readyz")).status_code == 200

    consumer.ready = False
    assert (await client.get("/readyz")).json() == {"status": "nats_unavailable"}

    consumer.ready = True
    store.healthy = False
    assert (await client.get("/readyz")).json() == {"status": "database_unavailable"}


async def test_readiness_fails_while_shutting_down(client):
    client.app.state.shutting_down = True
    assert (await client.get("/readyz")).status_code == 503


async def test_exposes_metrics(client):
    res = await client.get("/metrics")
    assert res.status_code == 200
    assert "notification_events_processed_total" in res.text

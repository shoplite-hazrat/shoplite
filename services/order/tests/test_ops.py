import pytest

pytestmark = pytest.mark.anyio


async def test_liveness_ignores_dependencies(client, repo):
    repo.healthy = False
    assert (await client.get("/healthz")).status_code == 200


async def test_readiness_reflects_database(client, repo):
    assert (await client.get("/readyz")).status_code == 200
    repo.healthy = False
    res = await client.get("/readyz")
    assert res.status_code == 503
    assert res.json() == {"status": "database_unavailable"}


async def test_readiness_fails_while_shutting_down(client, app):
    app.state.shutting_down = True
    res = await client.get("/readyz")
    assert res.status_code == 503
    assert res.json() == {"status": "shutting_down"}


async def test_echoes_request_id(client):
    res = await client.get("/healthz", headers={"x-request-id": "abc-123"})
    assert res.headers["x-request-id"] == "abc-123"


async def test_generates_request_id_when_missing(client):
    res = await client.get("/healthz")
    assert len(res.headers["x-request-id"]) == 36


async def test_metrics_use_route_templates(client):
    await client.get("/v1/orders/00000000-0000-0000-0000-000000000000")
    body = (await client.get("/metrics")).text
    assert 'route="/v1/orders/{order_id}"' in body
    assert "00000000-0000-0000-0000-000000000000" not in body

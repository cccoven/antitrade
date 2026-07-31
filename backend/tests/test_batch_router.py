import pytest
from httpx import AsyncClient, ASGITransport

from main import app
from db import get_db


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(db):
    app.dependency_overrides[get_db] = lambda: db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_headers(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "batch@example.com", "password": "secret123"},
    )
    assert resp.status_code == 200
    token = resp.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


async def _mk(client, headers, symbol, direction="long", tags=None):
    resp = await client.post(
        "/api/journal/trades",
        json={
            "symbol": symbol, "direction": direction,
            "tags": tags or [],
            "open_time": "2026-01-10T00:00:00+00:00",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    return resp.json()["data"]


# ── POST /trades/batch/delete ───────────────────────────────

@pytest.mark.anyio
async def test_batch_delete_by_ids(client, auth_headers):
    t1 = await _mk(client, auth_headers, "BTCUSD")
    t2 = await _mk(client, auth_headers, "ETHUSD")
    await _mk(client, auth_headers, "XAUUSD")

    resp = await client.post(
        "/api/journal/trades/batch/delete",
        json={"trade_ids": [t1["id"], t2["id"]]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] == 2


@pytest.mark.anyio
async def test_batch_delete_by_filter_select_all_matching(client, auth_headers):
    await _mk(client, auth_headers, "BTCUSD", direction="short")
    await _mk(client, auth_headers, "ETHUSD", direction="short")
    await _mk(client, auth_headers, "XAUUSD", direction="long")

    resp = await client.post(
        "/api/journal/trades/batch/delete",
        json={"select_all_matching": True, "filter": {"direction": "short"}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] == 2


@pytest.mark.anyio
async def test_batch_delete_empty_target_is_400(client, auth_headers):
    resp = await client.post(
        "/api/journal/trades/batch/delete",
        json={"trade_ids": []},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_batch_delete_without_auth_is_401(client):
    resp = await client.post(
        "/api/journal/trades/batch/delete",
        json={"trade_ids": ["x"]},
    )
    assert resp.status_code == 401


# ── POST /trades/batch/tag ──────────────────────────────────

@pytest.mark.anyio
async def test_batch_tag_adds_and_dedups(client, auth_headers):
    t1 = await _mk(client, auth_headers, "BTCUSD", tags=["a", "b"])
    t2 = await _mk(client, auth_headers, "ETHUSD", tags=[])

    resp = await client.post(
        "/api/journal/trades/batch/tag",
        json={"trade_ids": [t1["id"], t2["id"]], "tags": ["b", "c"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["updated"] == 2

    r1 = await client.get(f"/api/journal/trades/{t1['id']}", headers=auth_headers)
    assert r1.json()["data"]["tags"] == ["a", "b", "c"]
    r2 = await client.get(f"/api/journal/trades/{t2['id']}", headers=auth_headers)
    assert r2.json()["data"]["tags"] == ["b", "c"]


@pytest.mark.anyio
async def test_batch_tag_empty_tags_is_400(client, auth_headers):
    t = await _mk(client, auth_headers, "BTCUSD")
    resp = await client.post(
        "/api/journal/trades/batch/tag",
        json={"trade_ids": [t["id"]], "tags": []},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_batch_tag_select_all_matching_path(client, auth_headers):
    await _mk(client, auth_headers, "BTCUSD", direction="short")
    await _mk(client, auth_headers, "ETHUSD", direction="short")

    resp = await client.post(
        "/api/journal/trades/batch/tag",
        json={
            "select_all_matching": True,
            "filter": {"direction": "short"},
            "tags": ["reviewed"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["updated"] == 2


# ── POST /trades/export ─────────────────────────────────────

@pytest.mark.anyio
async def test_export_selected_by_ids_returns_csv(client, auth_headers):
    t1 = await _mk(client, auth_headers, "BTCUSD")
    t2 = await _mk(client, auth_headers, "ETHUSD")
    await _mk(client, auth_headers, "XAUUSD")

    resp = await client.post(
        "/api/journal/trades/export",
        json={"trade_ids": [t1["id"], t2["id"]], "format": "csv"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    body = resp.text
    assert "BTCUSD" in body and "ETHUSD" in body
    assert "XAUUSD" not in body
    assert "currency_code" in body.splitlines()[0]


@pytest.mark.anyio
async def test_export_by_filter_select_all_matching(client, auth_headers):
    await _mk(client, auth_headers, "BTCUSD", direction="short")
    await _mk(client, auth_headers, "ETHUSD", direction="long")

    resp = await client.post(
        "/api/journal/trades/export",
        json={"select_all_matching": True, "filter": {"direction": "short"}, "format": "csv"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.text
    assert "BTCUSD" in body
    assert "ETHUSD" not in body

import pytest
from httpx import AsyncClient, ASGITransport

from main import app
from db import get_db


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(db):
    """AsyncClient with a transactional test session injected for all DB deps."""
    app.dependency_overrides[get_db] = lambda: db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_headers(client: AsyncClient):
    """Register a test user and return Authorization headers."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": "journal@example.com", "password": "secret123"},
    )
    assert resp.status_code == 200
    token = resp.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_trade(client: AsyncClient, auth_headers, **overrides):
    """Helper: POST a trade and return the response data dict."""
    payload = {
        "symbol": "XAUUSD",
        "direction": "long",
        "open_price": 1900.50,
        "quantity": 1.0,
        "open_time": "2025-01-10T09:00:00Z",
    }
    payload.update(overrides)
    resp = await client.post("/api/journal/trades", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    return body["data"]


@pytest.mark.anyio
async def test_create_trade(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/journal/trades",
        json={
            "symbol": "XAUUSD",
            "direction": "long",
            "open_price": 1900.50,
            "quantity": 1.0,
            "open_time": "2025-01-10T09:00:00Z",
        },
        headers=auth_headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["id"]
    assert body["data"]["symbol"] == "XAUUSD"
    assert body["data"]["direction"] == "long"
    assert body["data"]["open_price"] == 1900.50


@pytest.mark.anyio
async def test_list_trades(client: AsyncClient, auth_headers):
    await _create_trade(client, auth_headers)
    resp = await client.get("/api/journal/trades", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert isinstance(body["data"]["items"], list)
    assert len(body["data"]["items"]) >= 1


@pytest.mark.anyio
async def test_get_trade(client: AsyncClient, auth_headers):
    trade = await _create_trade(client, auth_headers, symbol="BTCUSD")
    resp = await client.get(f"/api/journal/trades/{trade['id']}", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["symbol"] == "BTCUSD"


@pytest.mark.anyio
async def test_update_trade(client: AsyncClient, auth_headers):
    trade = await _create_trade(client, auth_headers)
    resp = await client.put(
        f"/api/journal/trades/{trade['id']}",
        json={"close_price": 1950.0, "pnl": 49.50},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["close_price"] == 1950.0
    assert body["data"]["pnl"] == 49.50


@pytest.mark.anyio
async def test_delete_trade(client: AsyncClient, auth_headers):
    trade = await _create_trade(client, auth_headers)
    resp = await client.delete(f"/api/journal/trades/{trade['id']}", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0


@pytest.mark.anyio
async def test_get_stats(client: AsyncClient, auth_headers):
    resp = await client.get("/api/journal/stats", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert "total_trades" in body["data"]
    assert "equity_curve" in body["data"]


@pytest.mark.anyio
async def test_export_csv(client: AsyncClient, auth_headers):
    await _create_trade(client, auth_headers)
    resp = await client.get("/api/journal/export?format=csv", headers=auth_headers)

    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    # Should contain header row and at least one data row
    lines = resp.text.strip().split("\n")
    assert len(lines) >= 2
    assert "currency_code" in lines[0]


@pytest.mark.anyio
async def test_validation_error(client: AsyncClient, auth_headers):
    resp = await client.post("/api/journal/trades", json={}, headers=auth_headers)

    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 400


@pytest.mark.anyio
async def test_unauthorized_without_token(client: AsyncClient):
    resp = await client.get("/api/journal/trades")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_create_diagnosis_job(client: AsyncClient, auth_headers, monkeypatch):
    import config
    monkeypatch.setattr(config, "LLM_PROVIDER", "demo")

    resp = await client.post(
        "/api/journal/diagnosis",
        json={"lang": "en"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["job_id"]


@pytest.mark.anyio
async def test_get_calendar_summary(client: AsyncClient, auth_headers):
    await _create_trade(
        client,
        auth_headers,
        symbol="XAUUSD",
        pnl=10.0,
        close_time="2026-02-03T10:00:00Z",
        open_time="2026-02-03T09:00:00Z",
    )
    await _create_trade(
        client,
        auth_headers,
        symbol="BTCUSD",
        pnl=-4.0,
        close_time="2026-02-05T10:00:00Z",
        open_time="2026-02-05T09:00:00Z",
    )
    resp = await client.get("/api/journal/calendar?month=2026-02", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["month"] == "2026-02"
    assert isinstance(body["data"]["days"], list)
    assert isinstance(body["data"]["weeks"], list)
    assert any(day["date"] == "2026-02-03" for day in body["data"]["days"])


@pytest.mark.anyio
async def test_settings_get_defaults_to_null(client: AsyncClient, auth_headers):
    resp = await client.get("/api/journal/settings", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["starting_capital"] is None
    assert body["data"]["currency_code"] is None


@pytest.mark.anyio
async def test_settings_put_and_get_roundtrip(client: AsyncClient, auth_headers):
    resp = await client.put(
        "/api/journal/settings",
        headers=auth_headers,
        json={"starting_capital": 50000.0},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["starting_capital"] == 50000.0

    resp = await client.get("/api/journal/settings", headers=auth_headers)
    assert resp.json()["data"]["starting_capital"] == 50000.0


@pytest.mark.anyio
async def test_settings_put_null_clears(client: AsyncClient, auth_headers):
    await client.put(
        "/api/journal/settings",
        headers=auth_headers,
        json={"starting_capital": 50000.0},
    )
    resp = await client.put(
        "/api/journal/settings",
        headers=auth_headers,
        json={"starting_capital": None},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["starting_capital"] is None


@pytest.mark.anyio
async def test_settings_patch_currency_preserves_starting_capital(client: AsyncClient, auth_headers):
    await client.put(
        "/api/journal/settings",
        headers=auth_headers,
        json={"starting_capital": 50000.0},
    )
    resp = await client.patch(
        "/api/journal/settings",
        headers=auth_headers,
        json={"currency_code": "USD"},
    )

    assert resp.status_code == 200
    assert resp.json()["data"] == {
        "starting_capital": 50000.0,
        "currency_code": "USD",
    }


@pytest.mark.anyio
async def test_settings_rejects_unsupported_currency(client: AsyncClient, auth_headers):
    resp = await client.patch(
        "/api/journal/settings",
        headers=auth_headers,
        json={"currency_code": "BTC"},
    )

    assert resp.status_code == 400
    assert resp.json()["code"] == 400


@pytest.mark.anyio
async def test_settings_put_rejects_negative(client: AsyncClient, auth_headers):
    resp = await client.put(
        "/api/journal/settings",
        headers=auth_headers,
        json={"starting_capital": -100.0},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 400


async def _register_other(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "password": "secret123"},
    )
    return {"Authorization": f"Bearer {resp.json()['data']['token']}"}


@pytest.mark.anyio
async def test_post_trade_with_strategy_id_persists(client: AsyncClient, auth_headers):
    sid = (await client.post("/api/strategies", json={"title": "S"}, headers=auth_headers)).json()["data"]["id"]
    r = await client.post(
        "/api/journal/trades",
        json={"symbol": "XAUUSD", "direction": "long", "strategy_id": sid},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["data"]["strategy_id"] == sid


@pytest.mark.anyio
async def test_post_trade_with_invalid_strategy_returns_400(client: AsyncClient, auth_headers):
    r = await client.post(
        "/api/journal/trades",
        json={"symbol": "XAUUSD", "direction": "long", "strategy_id": "does-not-exist"},
        headers=auth_headers,
    )
    assert r.status_code == 400


@pytest.mark.anyio
async def test_post_trade_with_other_users_strategy_returns_400(client: AsyncClient, auth_headers):
    other = await _register_other(client)
    sid = (await client.post("/api/strategies", json={"title": "S"}, headers=other)).json()["data"]["id"]
    r = await client.post(
        "/api/journal/trades",
        json={"symbol": "XAUUSD", "direction": "long", "strategy_id": sid},
        headers=auth_headers,
    )
    assert r.status_code == 400


@pytest.mark.anyio
async def test_list_trades_includes_strategy_id(client: AsyncClient, auth_headers):
    sid = (await client.post("/api/strategies", json={"title": "S"}, headers=auth_headers)).json()["data"]["id"]
    await client.post(
        "/api/journal/trades",
        json={"symbol": "XAUUSD", "direction": "long", "strategy_id": sid},
        headers=auth_headers,
    )
    items = (await client.get("/api/journal/trades", headers=auth_headers)).json()["data"]["items"]
    assert items[0]["strategy_id"] == sid


@pytest.mark.anyio
async def test_delete_strategy_nulls_referencing_trade(client: AsyncClient, auth_headers):
    sid = (await client.post("/api/strategies", json={"title": "S"}, headers=auth_headers)).json()["data"]["id"]
    tid = (await client.post(
        "/api/journal/trades",
        json={"symbol": "XAUUSD", "direction": "long", "strategy_id": sid},
        headers=auth_headers,
    )).json()["data"]["id"]
    await client.delete(f"/api/strategies/{sid}", headers=auth_headers)
    trade = (await client.get(f"/api/journal/trades/{tid}", headers=auth_headers)).json()["data"]
    assert trade["strategy_id"] is None

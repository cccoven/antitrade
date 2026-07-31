import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_market_overview_is_public(monkeypatch):
    monkeypatch.setattr("routers.market.get_market_overview_snapshot", lambda: {
        "quotes": {"provider": "twelve_data", "items": []},
        "macro": [],
        "states": {},
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/market/overview")

    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert response.json()["data"]["quotes"]["provider"] == "twelve_data"


@pytest.mark.anyio
async def test_market_overview_can_force_refresh(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "routers.market.refresh_market_overview_snapshot",
        lambda force_refresh: calls.append(force_refresh) or {
            "quotes": {"provider": "gateway", "items": [{"symbol": "NQ"}]},
            "macro": [],
            "states": {},
        },
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/market/overview?force_refresh=true")

    assert response.status_code == 200
    assert calls == [True]
    assert response.json()["data"]["quotes"]["items"][0]["symbol"] == "NQ"


@pytest.mark.anyio
async def test_daily_market_briefing_is_public(monkeypatch):
    async def fake_briefing(session, lang, force_refresh):
        return {
            "generated_at": "2026-07-16T00:00:00+00:00",
            "summary": "Market signals are mixed.",
            "regime": {"bias": "neutral"},
            "lang": lang,
            "forced": force_refresh,
        }

    monkeypatch.setattr("routers.market.get_daily_market_briefing", fake_briefing)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/market/daily-briefing?lang=en&force_refresh=true")

    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert response.json()["data"]["lang"] == "en"
    assert response.json()["data"]["forced"] is True


@pytest.mark.anyio
async def test_market_hours_is_public(monkeypatch):
    monkeypatch.setattr("routers.market.get_market_hours", lambda timezone_name: {
        "reference_timezone": timezone_name,
        "active_count": 3,
        "markets": [],
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/market/hours?timezone=Europe/London")

    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert response.json()["data"]["reference_timezone"] == "Europe/London"


@pytest.mark.anyio
async def test_instrument_search_returns_canonical_series_identity():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/market/instruments?q=XAUUSD&asset_class=spot",
        )

    assert response.status_code == 200
    match = response.json()["data"]["items"][0]
    assert match == {
        "series_id": "series:spot:xau-usd:consolidated",
        "symbol": "XAU/USD",
        "name": "Gold Spot / U.S. Dollar",
        "asset_class": "spot",
        "venue": None,
        "series_kind": "consolidated",
    }


@pytest.mark.anyio
async def test_instrument_search_surfaces_ambiguous_crypto_candidates():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/market/instruments?q=BTCUSD&asset_class=crypto",
        )

    items = response.json()["data"]["items"]
    assert {item["venue"] for item in items} == {None, "BINANCE", "COINBASE"}

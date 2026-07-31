import pytest
from httpx import ASGITransport, AsyncClient

from auth_dependency import get_current_user
from main import app
from routers.replay import _get_journal_svc, _get_replay_svc
from services.replay import ReplayProblem


TRADE = {
    "id": "trade-1",
    "symbol": "BTCUSD",
    "series_id": "series:crypto:btc-usd:coinbase",
    "exchange": "COINBASE",
    "direction": "long",
    "open_time": "2026-01-10T00:00:00+00:00",
    "close_time": "2026-01-10T05:00:00+00:00",
    "open_price": 100.0,
    "close_price": 110.0,
    "pnl": 10.0,
}

FAKE_BUNDLE = {
    "trade": TRADE,
    "instrument": {
        "series_id": TRADE["series_id"],
        "display_symbol": "BTCUSD",
        "venue": "COINBASE",
        "fidelity": "exact",
    },
    "meta": {
        "requested_interval": "auto",
        "interval": "60",
        "window": "standard",
        "series_id": TRADE["series_id"],
        "data_source": "fixture",
        "cache_status": "miss",
        "quality_warnings": [],
        "coverage_start": "2026-01-09T00:00:00+00:00",
        "coverage_end": "2026-01-11T00:00:00+00:00",
        "bar_count": 1,
        "start_index": 1,
        "decision_index": 0,
    },
    "bars": [
        {
            "time": 1,
            "open": 1.0,
            "high": 1.0,
            "low": 1.0,
            "close": 1.0,
            "volume": 1.0,
        }
    ],
    "open_index": 0,
    "close_index": 0,
}


class FakeJournalService:
    def __init__(self, trade=TRADE):
        self.trade = trade

    def get_trade(self, trade_id, user_id):
        if self.trade is None or trade_id != self.trade["id"]:
            return None
        return self.trade


class FakeReplayService:
    def __init__(self, result=FAKE_BUNDLE, problem=None):
        self.result = result
        self.problem = problem

    def prepare(self, trade, interval, window):
        if self.problem:
            raise self.problem
        return self.result


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    app.dependency_overrides[get_current_user] = lambda: "user-1"
    app.dependency_overrides[_get_journal_svc] = lambda: FakeJournalService()
    app.dependency_overrides[_get_replay_svc] = lambda: FakeReplayService()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_get_replay_returns_bundle(client):
    response = await client.get("/api/replay/trade-1")

    assert response.status_code == 200
    assert response.json()["data"]["meta"]["data_source"] == "fixture"


@pytest.mark.anyio
async def test_get_replay_404_when_trade_missing(client):
    app.dependency_overrides[_get_journal_svc] = lambda: FakeJournalService(None)

    response = await client.get("/api/replay/no-such-id")

    assert response.status_code == 404
    assert response.json()["data"]["problem"] == "trade_not_found"


@pytest.mark.anyio
async def test_get_replay_401_without_auth(client):
    app.dependency_overrides.pop(get_current_user)

    response = await client.get("/api/replay/trade-1")

    assert response.status_code == 401


@pytest.mark.anyio
async def test_get_replay_returns_typed_problem(client):
    app.dependency_overrides[_get_replay_svc] = lambda: FakeReplayService(
        problem=ReplayProblem(
            "interval_unavailable",
            suggested_intervals=["60", "240"],
        ),
    )

    response = await client.get("/api/replay/trade-1?interval=15")

    assert response.status_code == 422
    assert response.json()["data"] == {
        "problem": "interval_unavailable",
        "retryable": False,
        "suggested_intervals": ["60", "240"],
    }


@pytest.mark.anyio
async def test_get_replay_does_not_expose_provider_error(client):
    app.dependency_overrides[_get_replay_svc] = lambda: FakeReplayService(
        problem=ReplayProblem(
            "coverage_unavailable",
            status_code=503,
            retryable=True,
        ),
    )

    response = await client.get("/api/replay/trade-1")

    assert response.status_code == 503
    assert response.json()["message"] == "replay_unavailable"
    assert "provider" not in response.text.lower()

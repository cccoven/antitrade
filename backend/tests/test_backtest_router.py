from datetime import datetime, timezone

import pytest
from httpx import AsyncClient, ASGITransport

from main import app
from db import get_db
from auth_dependency import get_current_user
from models import BacktestRun, User
from services.backtest import BacktestService


TEST_USER_ID = "backtest-test-user"

SAMPLE_CONFIG = {
    "symbol": "XAUUSD",
    "interval": "D",
    "direction": "long",
    "stop_loss": 2.0,
    "take_profit": 4.0,
    "entry_conditions": [
        {
            "left": {"type": "ema", "params": {"period": 10}},
            "operator": "cross_above",
            "right": {"type": "ema", "params": {"period": 20}},
        }
    ],
    "exit_conditions": [],
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(db, monkeypatch):
    """AsyncClient with session-overridden db and a fixed test user."""
    now = datetime.now(timezone.utc).isoformat()
    db.add(User(id=TEST_USER_ID, email="backtest@example.com", password="x", name="", created_at=now))
    db.flush()
    monkeypatch.setattr(
        BacktestService,
        "_schedule_run",
        staticmethod(lambda _run_id: None),
    )

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def unauthed_client(db):
    """AsyncClient with db override but NO get_current_user override — triggers 401."""
    app.dependency_overrides[get_db] = lambda: db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.pop(get_db, None)


async def _create_strategy(client: AsyncClient, **overrides):
    """Helper: POST a strategy and return the response data dict."""
    payload = {"name": "Test Strategy", "config": SAMPLE_CONFIG}
    payload.update(overrides)
    resp = await client.post("/api/backtest/strategies", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    return body["data"]


# ------------------------------------------------------------------
# Strategy CRUD endpoints
# ------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_strategy(client: AsyncClient):
    resp = await client.post(
        "/api/backtest/strategies",
        json={"name": "My Strategy", "config": SAMPLE_CONFIG},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["id"]
    assert body["data"]["name"] == "My Strategy"
    assert body["data"]["config"]["schema_version"] == 2
    assert body["data"]["config"]["series_id"] == "series:spot:xau-usd:consolidated"
    assert body["data"]["config"]["stop_loss_pct"] == 2.0
    assert body["data"]["config"]["take_profit_pct"] == 4.0


@pytest.mark.anyio
async def test_create_strategy_rejects_invalid_config(client: AsyncClient):
    response = await client.post(
        "/api/backtest/strategies",
        json={"name": "Invalid", "config": {"symbol": "XAUUSD", "position_size": -1}},
    )

    assert response.status_code == 400
    assert response.json()["code"] == 400


@pytest.mark.anyio
async def test_create_strategy_rejects_unknown_market_series(client: AsyncClient):
    response = await client.post(
        "/api/backtest/strategies",
        json={
            "name": "Invalid",
            "config": {
                **SAMPLE_CONFIG,
                "series_id": "series:missing",
            },
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == 400


@pytest.mark.anyio
async def test_list_strategies(client: AsyncClient):
    await _create_strategy(client, name="Strategy A")
    await _create_strategy(client, name="Strategy B")

    resp = await client.get("/api/backtest/strategies")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 2


@pytest.mark.anyio
async def test_update_strategy(client: AsyncClient):
    strategy = await _create_strategy(client)
    resp = await client.put(
        f"/api/backtest/strategies/{strategy['id']}",
        json={"name": "Updated Name"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["name"] == "Updated Name"


@pytest.mark.anyio
async def test_update_strategy_not_found(client: AsyncClient):
    resp = await client.put(
        "/api/backtest/strategies/nonexistent",
        json={"name": "X"},
    )

    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_strategy(client: AsyncClient):
    strategy = await _create_strategy(client)
    resp = await client.delete(
        f"/api/backtest/strategies/{strategy['id']}",
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0


@pytest.mark.anyio
async def test_delete_strategy_not_found(client: AsyncClient):
    resp = await client.delete(
        "/api/backtest/strategies/nonexistent",
    )

    assert resp.status_code == 404


# ------------------------------------------------------------------
# Backtest run/poll endpoints
# ------------------------------------------------------------------


@pytest.mark.anyio
async def test_run_backtest_returns_job_id(client: AsyncClient):
    strategy = await _create_strategy(client)

    resp = await client.post(
        "/api/backtest/runs",
        json={
            "strategy_id": strategy["id"],
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["job_id"]
    assert body["data"]["run_id"] == body["data"]["job_id"]
    assert body["data"]["status"] == "queued"
    assert body["data"]["requested_date_from"] == "2025-01-01"


@pytest.mark.anyio
async def test_run_backtest_strategy_not_found(client: AsyncClient):
    resp = await client.post(
        "/api/backtest/runs",
        json={"strategy_id": "nonexistent"},
    )

    assert resp.status_code == 404


@pytest.mark.anyio
async def test_poll_backtest_job(client: AsyncClient):
    strategy = await _create_strategy(client)

    run_resp = await client.post(
        "/api/backtest/runs",
        json={"strategy_id": strategy["id"]},
    )
    job_id = run_resp.json()["data"]["job_id"]

    resp = await client.get(f"/api/backtest/runs/{job_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["job_id"] == job_id
    assert body["data"]["status"] == "queued"


@pytest.mark.anyio
async def test_list_rerun_and_delete_backtest_runs(client: AsyncClient, db):
    strategy = await _create_strategy(client)
    created = (
        await client.post(
            "/api/backtest/runs",
            json={"strategy_id": strategy["id"]},
        )
    ).json()["data"]

    listed = await client.get("/api/backtest/runs")
    assert listed.status_code == 200
    assert listed.json()["data"]["items"][0]["id"] == created["id"]
    assert listed.json()["data"]["total"] == 1

    rerun = await client.post(f"/api/backtest/runs/{created['id']}/rerun")
    assert rerun.status_code == 200
    assert rerun.json()["data"]["id"] != created["id"]
    assert rerun.json()["data"]["strategy_config"] == created["strategy_config"]

    # Running records cannot be deleted; finished records can.
    blocked = await client.delete(f"/api/backtest/runs/{created['id']}")
    assert blocked.status_code == 404

    persisted = db.get(BacktestRun, created["id"])
    persisted.status = "completed"
    db.commit()
    deleted = await client.delete(f"/api/backtest/runs/{created['id']}")
    assert deleted.status_code == 200
    missing = await client.get(f"/api/backtest/runs/{created['id']}")
    assert missing.status_code == 404


@pytest.mark.anyio
async def test_list_backtest_runs_is_paginated(client: AsyncClient):
    strategy = await _create_strategy(client)
    created_ids = []
    for _ in range(3):
        created = (
            await client.post(
                "/api/backtest/runs",
                json={"strategy_id": strategy["id"]},
            )
        ).json()["data"]
        created_ids.append(created["id"])

    response = await client.get(
        "/api/backtest/runs",
        params={"limit": 2, "offset": 1},
    )

    assert response.status_code == 200
    page = response.json()["data"]
    assert page["total"] == 3
    assert page["limit"] == 2
    assert page["offset"] == 1
    assert len(page["items"]) == 2
    assert {item["id"] for item in page["items"]}.issubset(set(created_ids))


@pytest.mark.anyio
async def test_create_run_rejects_reversed_dates(client: AsyncClient):
    strategy = await _create_strategy(client)
    response = await client.post(
        "/api/backtest/runs",
        json={
            "strategy_id": strategy["id"],
            "date_from": "2025-12-31",
            "date_to": "2025-01-01",
        },
    )

    assert response.status_code == 400


@pytest.mark.anyio
async def test_create_optimization_validation_and_walk_forward_runs(
    client: AsyncClient,
):
    strategy = await _create_strategy(client)
    grid = [{"parameter": "stop_loss_pct", "values": [1, 2, 3]}]

    optimization = await client.post(
        "/api/backtest/runs/optimization",
        json={
            "strategy_id": strategy["id"],
            "objective": "sharpe_ratio",
            "grids": grid,
        },
    )
    assert optimization.status_code == 200
    assert optimization.json()["data"]["run_kind"] == "optimization"

    validation = await client.post(
        "/api/backtest/runs/validation",
        json={"strategy_id": strategy["id"], "train_ratio": 0.7},
    )
    assert validation.status_code == 200
    assert validation.json()["data"]["run_kind"] == "validation"

    walk_forward = await client.post(
        "/api/backtest/runs/walk-forward",
        json={
            "strategy_id": strategy["id"],
            "objective": "total_return_pct",
            "grids": grid,
            "train_bars": 100,
            "test_bars": 20,
            "step_bars": 20,
        },
    )
    assert walk_forward.status_code == 200
    assert walk_forward.json()["data"]["run_kind"] == "walk_forward"


@pytest.mark.anyio
async def test_optimization_rejects_more_than_two_hundred_trials(
    client: AsyncClient,
):
    strategy = await _create_strategy(client)
    response = await client.post(
        "/api/backtest/runs/optimization",
        json={
            "strategy_id": strategy["id"],
            "grids": [
                {"parameter": "stop_loss_pct", "values": list(range(1, 16))},
                {"parameter": "take_profit_pct", "values": list(range(1, 16))},
            ],
        },
    )

    assert response.status_code == 400


@pytest.mark.anyio
async def test_optimization_accepts_two_hundred_trials_and_rejects_duplicates(
    client: AsyncClient,
):
    strategy = await _create_strategy(client)
    accepted = await client.post(
        "/api/backtest/runs/optimization",
        json={
            "strategy_id": strategy["id"],
            "grids": [
                {
                    "parameter": "stop_loss_pct",
                    "values": list(range(1, 201)),
                },
            ],
        },
    )
    assert accepted.status_code == 200

    duplicate = await client.post(
        "/api/backtest/runs/optimization",
        json={
            "strategy_id": strategy["id"],
            "grids": [
                {"parameter": "stop_loss_pct", "values": [1, 2]},
                {"parameter": "stop_loss_pct", "values": [3, 4]},
            ],
        },
    )
    assert duplicate.status_code == 400


@pytest.mark.anyio
async def test_poll_job_not_found(client: AsyncClient):
    resp = await client.get("/api/backtest/runs/nonexistent")

    assert resp.status_code == 404


# ------------------------------------------------------------------
# Auth required
# ------------------------------------------------------------------


@pytest.mark.anyio
async def test_unauthorized_without_token(unauthed_client: AsyncClient):
    resp = await unauthed_client.get("/api/backtest/strategies")
    assert resp.status_code == 401

    resp = await unauthed_client.post("/api/backtest/strategies", json={"name": "X", "config": {}})
    assert resp.status_code == 401

    resp = await unauthed_client.post("/api/backtest/run", json={"strategy_id": "x"})
    assert resp.status_code == 401

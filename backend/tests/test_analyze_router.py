from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

import routers.analyze as analyze_router
from auth_dependency import get_current_user
from db import get_db
from main import app


@dataclass
class FakeJob:
    job_id: str
    symbol: str
    exchange: str
    interval: str
    status: str
    created_at: str
    updated_at: str
    analysis: str | None = None
    analyzed_at: str | None = None
    error: str | None = None


@pytest.fixture(autouse=True)
def billing_dependencies(db, user_id):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user_id
    yield
    app.dependency_overrides.clear()


def test_create_job_returns_wrapped_job(monkeypatch):
    fake_job = FakeJob(
        job_id="job-1",
        symbol="BTCUSD",
        exchange="COINBASE",
        interval="240",
        status="queued",
        created_at="2025-01-01T00:00:00+00:00",
        updated_at="2025-01-01T00:00:00+00:00",
    )
    monkeypatch.setattr(analyze_router, "create_analysis_job", lambda **_: fake_job)

    with TestClient(app) as client:
        response = client.post(
            "/api/analyze/jobs",
            json={
                "symbol": "BTCUSD",
                "exchange": "COINBASE",
                "interval": "240",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["message"] == "ok"
    assert payload["data"]["job_id"] == "job-1"
    assert payload["data"]["status"] == "queued"


def test_get_job_returns_null_when_missing(monkeypatch):
    monkeypatch.setattr(analyze_router, "get_analysis_job", lambda _: None)

    with TestClient(app) as client:
        response = client.get("/api/analyze/jobs/missing-job")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"] is None


def test_get_latest_returns_cached_analysis(monkeypatch):
    latest = analyze_router.LatestAnalyzeResponse(
        symbol="BTCUSD",
        exchange="COINBASE",
        interval="240",
        analysis="cached markdown",
        analyzed_at="2025-01-01T00:00:00+00:00",
    )
    monkeypatch.setattr(analyze_router, "get_latest_analysis", lambda **_: latest)

    with TestClient(app) as client:
        response = client.get(
            "/api/analyze/latest",
            params={"symbol": "BTCUSD", "exchange": "COINBASE", "interval": "240"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["analysis"] == "cached markdown"


def test_validation_error_uses_api_response_wrapper():
    with TestClient(app) as client:
        response = client.post("/api/analyze/jobs", json={})

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == 400
    assert payload["data"] is None
    assert payload["message"]

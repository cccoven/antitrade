import pytest
from datetime import datetime, timedelta, timezone
from httpx import ASGITransport, AsyncClient

from main import app
from db import get_db
from models import BillingAccount


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(db, tmp_path, monkeypatch):
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_headers(client: AsyncClient, db):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "review@example.com", "password": "secret123"},
    )
    assert resp.status_code == 200
    user_id = resp.json()["data"]["user"]["id"]
    now = datetime.now(timezone.utc)
    db.add(BillingAccount(
        user_id=user_id,
        plan="pro",
        status="active",
        current_period_start=now.isoformat(),
        current_period_end=(now + timedelta(days=30)).isoformat(),
        cancel_at_period_end=False,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    ))
    db.commit()
    return {"Authorization": f"Bearer {resp.json()['data']['token']}"}


@pytest.mark.anyio
async def test_get_missing_review_returns_empty_draft(client, auth_headers):
    resp = await client.get("/api/journal/reviews/2026-04-24", headers=auth_headers)
    assert resp.status_code == 200
    review = resp.json()["data"]
    assert review["review_date"] == "2026-04-24"
    assert review["title"] == ""
    assert review["body"] == ""
    assert review["tags"] == []
    assert "market_context" not in review


@pytest.mark.anyio
async def test_put_review_creates_then_updates(client, auth_headers):
    resp = await client.put(
        "/api/journal/reviews/2026-04-24",
        headers=auth_headers,
        json={"title": "first", "body": "# heading\n\nbody text", "tags": ["foo"]},
    )
    assert resp.status_code == 200
    first = resp.json()["data"]
    assert first["title"] == "first"
    assert first["body"] == "# heading\n\nbody text"
    assert first["tags"] == ["foo"]

    resp = await client.put(
        "/api/journal/reviews/2026-04-24",
        headers=auth_headers,
        json={"title": "second", "body": "updated", "tags": []},
    )
    second = resp.json()["data"]
    assert second["title"] == "second"
    assert second["body"] == "updated"
    assert second["tags"] == []
    assert second["id"] == first["id"]


@pytest.mark.anyio
async def test_bundle_returns_review_stats_and_trades(client, auth_headers):
    await client.post(
        "/api/journal/trades",
        headers=auth_headers,
        json={
            "symbol": "XAUUSD",
            "direction": "long",
            "open_time": "2026-04-24T09:00:00Z",
            "close_time": "2026-04-24T10:00:00Z",
            "pnl": 25.0,
        },
    )
    resp = await client.get(
        "/api/journal/reviews/2026-04-24/bundle",
        headers=auth_headers,
        params={"date_from": "2026-04-24T00:00:00Z", "date_to": "2026-04-25T00:00:00Z"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["review"]["body"] == ""
    assert data["stats"]["total_trades"] == 1
    assert len(data["trades"]) == 1


@pytest.mark.anyio
async def test_bundle_with_no_trades_returns_empty(client, auth_headers):
    resp = await client.get(
        "/api/journal/reviews/2026-04-24/bundle",
        headers=auth_headers,
        params={"date_from": "2026-04-24T00:00:00Z", "date_to": "2026-04-25T00:00:00Z"},
    )
    data = resp.json()["data"]
    assert data["review"]["body"] == ""
    assert data["stats"]["total_trades"] == 0
    assert data["trades"] == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "action", ["title", "summary", "organize", "expand", "suggest"]
)
async def test_assist_actions_accepted(client, auth_headers, action, monkeypatch):
    class FakeProvider:
        async def complete(self, prompt: str) -> str:
            if action == "title":
                return '{"suggestions": ["a", "b", "c"]}'
            return '{"suggestions": ["one"]}'

    monkeypatch.setattr("services.analyzer.create_provider", lambda: FakeProvider())

    resp = await client.post(
        f"/api/journal/reviews/2026-04-24/assist",
        headers=auth_headers,
        json={
            "action": action,
            "body": "draft body",
            "selection": "x" if action in ("organize", "expand") else None,
            "date_from": "2026-04-24T00:00:00Z",
            "date_to": "2026-04-25T00:00:00Z",
            "lang": "zh",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["action"] == action
    if action == "title":
        assert len(data["suggestions"]) == 3
    else:
        assert len(data["suggestions"]) == 1


@pytest.mark.anyio
async def test_assist_invalid_action_rejected(client, auth_headers):
    resp = await client.post(
        "/api/journal/reviews/2026-04-24/assist",
        headers=auth_headers,
        json={
            "action": "bogus",
            "body": "",
            "date_from": "2026-04-24T00:00:00Z",
            "date_to": "2026-04-25T00:00:00Z",
        },
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_assist_provider_failure_returns_empty_suggestions(
    client, auth_headers, monkeypatch
):
    class FailingProvider:
        async def complete(self, prompt: str) -> str:
            raise RuntimeError("boom")

    monkeypatch.setattr("services.analyzer.create_provider", lambda: FailingProvider())

    resp = await client.post(
        "/api/journal/reviews/2026-04-24/assist",
        headers=auth_headers,
        json={
            "action": "summary",
            "body": "hi",
            "date_from": "2026-04-24T00:00:00Z",
            "date_to": "2026-04-25T00:00:00Z",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["suggestions"] == []


@pytest.mark.anyio
async def test_assist_requires_pro(client):
    registered = await client.post(
        "/api/auth/register",
        json={"email": "free-review@example.com", "password": "secret123"},
    )
    headers = {"Authorization": f"Bearer {registered.json()['data']['token']}"}

    response = await client.post(
        "/api/journal/reviews/2026-04-24/assist",
        headers=headers,
        json={
            "action": "summary",
            "body": "hi",
            "date_from": "2026-04-24T00:00:00Z",
            "date_to": "2026-04-25T00:00:00Z",
        },
    )

    assert response.status_code == 402
    assert response.json()["data"]["feature"] == "journal.ai_assist"

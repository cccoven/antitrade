import routers.chat as chat_router
import asyncio
import pytest
from db import get_db
from main import app
from fastapi.testclient import TestClient


def _auth(db, user_id):
    app.dependency_overrides[chat_router.get_current_user] = lambda: user_id
    app.dependency_overrides[get_db] = lambda: db


def test_create_then_list_conversations(db, user_id):
    _auth(db, user_id)
    try:
        with TestClient(app) as client:
            created = client.post("/api/chat/conversations").json()
            assert created["code"] == 0
            cid = created["data"]["id"]
            listed = client.get("/api/chat/conversations").json()
            assert [c["id"] for c in listed["data"]] == [cid]
    finally:
        app.dependency_overrides.clear()


def test_capabilities_expose_market_providers_and_new_commands(db, user_id):
    _auth(db, user_id)
    try:
        with TestClient(app) as client:
            response = client.get("/api/chat/capabilities")

            assert response.status_code == 200
            data = response.json()["data"]
            assert set(data["market_data"]) == {
                "stock", "forex", "crypto", "macro", "futures",
            }
            assert data["market_data"]["futures"] == {
                "configured": True,
                "provider": "market_gateway",
            }
            assert all(
                data["market_data"][asset]["configured"]
                for asset in ("stock", "forex", "crypto")
            )
            assert data["vision"] == {
                "available": False,
                "max_images": 4,
                "mime_types": ["image/png", "image/jpeg", "image/webp"],
            }
            assert {"/futures", "/check"} <= set(data["commands"])
    finally:
        app.dependency_overrides.clear()


def test_delete_conversation(db, user_id):
    _auth(db, user_id)
    try:
        with TestClient(app) as client:
            cid = client.post("/api/chat/conversations").json()["data"]["id"]
            resp = client.delete(f"/api/chat/conversations/{cid}")
            assert resp.json()["data"]["deleted"] is True
            assert client.get("/api/chat/conversations").json()["data"] == []
    finally:
        app.dependency_overrides.clear()


def test_update_conversation(db, user_id):
    _auth(db, user_id)
    try:
        with TestClient(app) as client:
            cid = client.post("/api/chat/conversations").json()["data"]["id"]
            resp = client.patch(
                f"/api/chat/conversations/{cid}",
                json={"title": "Renamed chat", "pinned": True},
            )
            assert resp.status_code == 200
            assert resp.json()["data"]["title"] == "Renamed chat"
            assert resp.json()["data"]["pinned_at"] is not None
    finally:
        app.dependency_overrides.clear()


def test_reorder_conversations(db, user_id):
    _auth(db, user_id)
    try:
        with TestClient(app) as client:
            first = client.post("/api/chat/conversations").json()["data"]
            second = client.post("/api/chat/conversations").json()["data"]
            resp = client.put(
                "/api/chat/conversations/order",
                json={"conversation_ids": [first["id"], second["id"]]},
            )
            assert resp.status_code == 200
            assert [item["id"] for item in resp.json()["data"]] == [
                first["id"], second["id"],
            ]
    finally:
        app.dependency_overrides.clear()


def test_get_messages_404_for_missing(db, user_id):
    _auth(db, user_id)
    try:
        with TestClient(app) as client:
            resp = client.get("/api/chat/conversations/nope/messages")
            assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_messages_returns_paginated_state(db, user_id):
    from services.chat import ChatService

    _auth(db, user_id)
    try:
        with TestClient(app) as client:
            cid = client.post("/api/chat/conversations").json()["data"]["id"]
            service = ChatService(db)
            service.add_message(cid, "user", "one")
            service.add_message(cid, "assistant", "two")
            service.add_message(cid, "user", "three")

            response = client.get(
                f"/api/chat/conversations/{cid}/messages?limit=2&offset=0",
            )

            data = response.json()["data"]
            assert [message["content"] for message in data["messages"]] == ["two", "three"]
            assert data["pending"] is None
            assert data["page"]["has_more"] is True
            assert data["page"]["next_offset"] == 2
    finally:
        app.dependency_overrides.clear()


def test_resume_decision_rejects_unknown_value(db, user_id):
    _auth(db, user_id)
    try:
        with TestClient(app) as client:
            cid = client.post("/api/chat/conversations").json()["data"]["id"]
            response = client.post(
                f"/api/chat/conversations/{cid}/resume",
                json={"decisions": [{"call_id": "call-1", "decision": "yes"}]},
            )
            assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


async def _slow_stream():
    await asyncio.sleep(0.02)
    yield "complete"


@pytest.mark.asyncio
async def test_sse_stream_sends_heartbeat_while_waiting(monkeypatch):
    monkeypatch.setattr(chat_router, "_SSE_HEARTBEAT_SECONDS", 0.005)
    events = []
    async for event in chat_router._sse_events(_slow_stream(), "en"):
        events.append(event)

    assert ": ping\n\n" in events
    assert any('"content": "complete"' in event for event in events)
    assert any('"type": "done"' in event for event in events)


def test_replace_last_message_requires_an_existing_user_message(db, user_id):
    _auth(db, user_id)
    try:
        with TestClient(app) as client:
            cid = client.post("/api/chat/conversations").json()["data"]["id"]
            resp = client.put(
                f"/api/chat/conversations/{cid}/messages/last",
                json={"content": "edited", "mode": "standard", "web_search": False},
            )
            assert resp.status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_research_mode_returns_structured_paywall_for_free_user(db, user_id):
    _auth(db, user_id)
    try:
        with TestClient(app) as client:
            cid = client.post("/api/chat/conversations").json()["data"]["id"]
            response = client.post(
                f"/api/chat/conversations/{cid}/messages",
                json={"content": "research this", "mode": "research", "web_search": False},
            )
        assert response.status_code == 402
        assert response.json()["data"]["feature"] == "assistant.research"
        assert response.json()["data"]["reason"] == "pro_required"
    finally:
        app.dependency_overrides.clear()

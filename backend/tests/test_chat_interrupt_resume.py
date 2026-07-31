import pytest
from datetime import datetime, timedelta, timezone

from models import ChatConversation
from services.chat import ChatService
from services.journal import JournalService
from services.memory import AssistantMemoryService
from tests._fake_chat_model import FakeDeleteThenAnswer, FakeRememberThenAnswer


def _seed_trade(db, user_id):
    return JournalService(db).create_trade(
        symbol="BTCUSD",
        direction="long",
        pnl=100.0,
        open_time="2026-01-01T00:00:00Z",
        close_time="2026-01-01T01:00:00Z",
        user_id=user_id,
    )


@pytest.mark.asyncio
async def test_write_tool_interrupts_and_persists_state(db, user_id, monkeypatch):
    trade = _seed_trade(db, user_id)
    monkeypatch.setattr("services.agent.create_model", lambda: FakeDeleteThenAnswer([trade["id"]]))
    svc = ChatService(db)
    conv = svc.create_conversation(user_id)

    events = []
    async for ev in svc.send_message(conv["id"], user_id, "删掉这笔", lang="zh"):
        events.append(ev)

    interrupts = [e for e in events if isinstance(e, dict) and e.get("type") == "interrupt"]
    assert len(interrupts) == 1
    assert interrupts[0]["items"][0]["tool_name"] == "delete_trades"
    assert JournalService(db).get_trade(trade["id"], user_id=user_id) is not None
    row = db.get(ChatConversation, conv["id"])
    assert row.pending_state is not None
    assert row.pending_state["options"] == {"mode": "standard", "web_search": False}
    assert row.pending_state["work"]["status"] == "interrupted"
    assert row.pending_state["work"]["items"][0]["status"] == "pending_approval"
    page = svc.get_message_page(conv["id"], user_id)
    assert page is not None
    assert page["pending"]["items"][0]["call_id"] == "call_del"
    assert page["pending"]["work"]["status"] == "interrupted"
    assert page["pending"]["expired"] is False


@pytest.mark.asyncio
async def test_resume_approve_executes_and_clears(db, user_id, monkeypatch):
    trade = _seed_trade(db, user_id)
    monkeypatch.setattr("services.agent.create_model", lambda: FakeDeleteThenAnswer([trade["id"]]))
    svc = ChatService(db)
    conv = svc.create_conversation(user_id)
    async for _ in svc.send_message(conv["id"], user_id, "删掉这笔", lang="zh"):
        pass

    text = []
    async for ev in svc.resume_run(
        conv["id"],
        user_id,
        [{"call_id": "call_del", "decision": "approve"}],
        lang="zh",
    ):
        if isinstance(ev, str):
            text.append(ev)

    assert JournalService(db).get_trade(trade["id"], user_id=user_id) is None
    row = db.get(ChatConversation, conv["id"])
    assert row.pending_state is None
    assert "".join(text) != ""
    assistant_message = svc.get_messages(conv["id"], user_id)[-1]
    assert assistant_message["work"]["status"] == "completed"
    assert assistant_message["work"]["items"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_resume_reject_keeps_data(db, user_id, monkeypatch):
    trade = _seed_trade(db, user_id)
    monkeypatch.setattr("services.agent.create_model", lambda: FakeDeleteThenAnswer([trade["id"]]))
    svc = ChatService(db)
    conv = svc.create_conversation(user_id)
    async for _ in svc.send_message(conv["id"], user_id, "删掉这笔", lang="zh"):
        pass

    async for _ in svc.resume_run(
        conv["id"],
        user_id,
        [{"call_id": "call_del", "decision": "reject"}],
        lang="zh",
    ):
        pass

    assert JournalService(db).get_trade(trade["id"], user_id=user_id) is not None
    row = db.get(ChatConversation, conv["id"])
    assert row.pending_state is None


@pytest.mark.asyncio
async def test_remember_memory_requires_confirmation(db, user_id, monkeypatch):
    content = "I prefer a maximum 1% risk per trade."
    monkeypatch.setattr("services.agent.create_model", lambda: FakeRememberThenAnswer(content))
    svc = ChatService(db)
    conv = svc.create_conversation(user_id)

    events = []
    async for ev in svc.send_message(conv["id"], user_id, "记住我的风险偏好", lang="zh"):
        events.append(ev)

    interrupts = [e for e in events if isinstance(e, dict) and e.get("type") == "interrupt"]
    assert interrupts[0]["items"][0]["tool_name"] == "remember_memory"
    assert AssistantMemoryService(db).list_memories(user_id) == []

    async for _ in svc.resume_run(
        conv["id"], user_id, [{"call_id": "call_mem", "decision": "approve"}], lang="zh",
    ):
        pass

    assert [m["content"] for m in AssistantMemoryService(db).list_memories(user_id)] == [content]


@pytest.mark.asyncio
async def test_new_message_discards_stale_pending(db, user_id, monkeypatch):
    trade = _seed_trade(db, user_id)
    monkeypatch.setattr("services.agent.create_model", lambda: FakeDeleteThenAnswer([trade["id"]]))
    svc = ChatService(db)
    conv = svc.create_conversation(user_id)
    async for _ in svc.send_message(conv["id"], user_id, "删掉这笔", lang="zh"):
        pass
    assert db.get(ChatConversation, conv["id"]).pending_state is not None

    from tests._fake_chat_model import FakeToolThenAnswer

    monkeypatch.setattr("services.agent.create_model", lambda: FakeToolThenAnswer())
    async for _ in svc.send_message(conv["id"], user_id, "我赚了多少", lang="zh"):
        pass
    assert db.get(ChatConversation, conv["id"]).pending_state is None


@pytest.mark.asyncio
async def test_resume_rejects_mismatched_decisions_without_consuming_pending(
    db, user_id, monkeypatch,
):
    trade = _seed_trade(db, user_id)
    monkeypatch.setattr("services.agent.create_model", lambda: FakeDeleteThenAnswer([trade["id"]]))
    svc = ChatService(db)
    conv = svc.create_conversation(user_id)
    async for _ in svc.send_message(conv["id"], user_id, "删掉这笔", lang="zh"):
        pass

    events = []
    async for event in svc.resume_run(
        conv["id"], user_id,
        [{"call_id": "wrong", "decision": "approve"}], lang="zh",
    ):
        events.append(event)

    assert events[-1]["code"] == "invalid_decisions"
    assert db.get(ChatConversation, conv["id"]).pending_state is not None
    assert JournalService(db).get_trade(trade["id"], user_id=user_id) is not None


@pytest.mark.asyncio
async def test_resume_expired_approval_never_executes(db, user_id, monkeypatch):
    trade = _seed_trade(db, user_id)
    monkeypatch.setattr("services.agent.create_model", lambda: FakeDeleteThenAnswer([trade["id"]]))
    svc = ChatService(db)
    conv = svc.create_conversation(user_id)
    async for _ in svc.send_message(conv["id"], user_id, "删掉这笔", lang="zh"):
        pass

    row = db.get(ChatConversation, conv["id"])
    row.pending_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    db.commit()

    events = []
    async for event in svc.resume_run(
        conv["id"], user_id,
        [{"call_id": "call_del", "decision": "approve"}], lang="zh",
    ):
        events.append(event)

    assert events[-1]["code"] == "pending_expired"
    assert db.get(ChatConversation, conv["id"]).pending_state is None
    assert JournalService(db).get_trade(trade["id"], user_id=user_id) is not None


@pytest.mark.asyncio
async def test_pending_state_is_claimed_only_once(db, user_id, monkeypatch):
    trade = _seed_trade(db, user_id)
    monkeypatch.setattr("services.agent.create_model", lambda: FakeDeleteThenAnswer([trade["id"]]))
    svc = ChatService(db)
    conv = svc.create_conversation(user_id)
    async for _ in svc.send_message(conv["id"], user_id, "删掉这笔", lang="zh"):
        pass

    row = db.get(ChatConversation, conv["id"])
    pending_at = row.pending_at
    assert svc._claim_pending(conv["id"], user_id, pending_at) is True
    assert svc._claim_pending(conv["id"], user_id, pending_at) is False


@pytest.mark.asyncio
async def test_stopping_stream_persists_closed_assistant_turn(db, user_id, monkeypatch):
    from tests._fake_chat_model import FakeToolThenAnswer

    monkeypatch.setattr("services.agent.create_model", lambda: FakeToolThenAnswer())
    svc = ChatService(db)
    conv = svc.create_conversation(user_id)
    stream = svc.send_message(conv["id"], user_id, "我赚了多少", lang="zh")

    first = await anext(stream)
    assert first["type"] == "work_start"
    await stream.aclose()

    messages = svc.get_messages(conv["id"], user_id)
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[-1]["content"] == "已停止生成。"
    assert messages[-1]["work"]["status"] == "error"

import pytest
from uuid import uuid4

from tests._fake_chat_model import FakeToolThenAnswer


def _add_image_asset(db, user_id, tmp_path, name: str):
    from models import UploadedAsset

    path = tmp_path / f"{name}.png"
    path.write_bytes(f"image-{name}".encode())
    asset = UploadedAsset(
        id=str(uuid4()), user_id=user_id, file_path=str(path),
        original_name=f"{name}.png", mime_type="image/png",
        width=1280, height=720, size_bytes=path.stat().st_size,
        created_at="2026-07-20T00:00:00+00:00",
    )
    db.add(asset)
    db.flush()
    return asset


def test_chat_tables_exist(db):
    from sqlalchemy import inspect
    names = set(inspect(db.bind).get_table_names())
    assert {"chat_conversations", "chat_messages", "chat_message_attachments"} <= names


@pytest.fixture
def chat_service(db, monkeypatch):
    from services.chat import ChatService
    svc = ChatService(db)
    monkeypatch.setattr("services.agent.create_model", lambda: FakeToolThenAnswer())
    return svc


def test_create_and_list_conversations(db, user_id):
    from services.chat import ChatService
    svc = ChatService(db)
    conv = svc.create_conversation(user_id)
    listed = svc.list_conversations(user_id)
    assert [c["id"] for c in listed] == [conv["id"]]
    assert listed[0]["pinned_at"] is None


def test_rename_and_pin_conversation(db, user_id):
    from services.chat import ChatService

    svc = ChatService(db)
    first = svc.create_conversation(user_id)
    second = svc.create_conversation(user_id)

    updated = svc.update_conversation(first["id"], user_id, title="Renamed", pinned=True)

    assert updated is not None
    assert updated["title"] == "Renamed"
    assert updated["pinned_at"] is not None
    assert [item["id"] for item in svc.list_conversations(user_id)] == [first["id"], second["id"]]

    unpinned = svc.update_conversation(first["id"], user_id, pinned=False)
    assert unpinned is not None and unpinned["pinned_at"] is None
    assert [item["id"] for item in svc.list_conversations(user_id)] == [second["id"], first["id"]]


def test_reorder_conversations_persists_within_pin_groups(db, user_id):
    from services.chat import ChatService

    svc = ChatService(db)
    first = svc.create_conversation(user_id, "First")
    second = svc.create_conversation(user_id, "Second")
    third = svc.create_conversation(user_id, "Third")
    svc.update_conversation(first["id"], user_id, pinned=True)

    reordered = svc.reorder_conversations(
        user_id,
        [first["id"], second["id"], third["id"]],
    )

    assert reordered is not None
    assert [item["id"] for item in reordered] == [first["id"], second["id"], third["id"]]
    assert [item["id"] for item in svc.list_conversations(user_id)] == [
        first["id"], second["id"], third["id"],
    ]

    svc.update_conversation(first["id"], user_id, pinned=False)
    assert [item["id"] for item in svc.list_conversations(user_id)] == [
        second["id"], third["id"], first["id"],
    ]


def test_reorder_conversations_rejects_stale_or_duplicate_ids(db, user_id):
    from services.chat import ChatService

    svc = ChatService(db)
    first = svc.create_conversation(user_id)
    second = svc.create_conversation(user_id)

    assert svc.reorder_conversations(user_id, [first["id"]]) is None
    assert svc.reorder_conversations(user_id, [first["id"], first["id"]]) is None
    assert [item["id"] for item in svc.list_conversations(user_id)] == [
        second["id"], first["id"],
    ]


def test_conversations_are_user_scoped(db, user_id):
    import uuid as _uuid
    from datetime import datetime, timezone
    from models import User
    from services.chat import ChatService
    other = str(_uuid.uuid4())
    db.add(User(
        id=other, email="o2@t.test", password="x", name="O",
        created_at=datetime.now(timezone.utc).isoformat(),
    ))
    db.flush()
    svc = ChatService(db)
    svc.create_conversation(other)
    assert svc.list_conversations(user_id) == []


def test_delete_conversation_cascades(db, user_id):
    from services.chat import ChatService
    svc = ChatService(db)
    conv = svc.create_conversation(user_id)
    svc.add_message(conv["id"], "user", "hi")
    assert svc.delete_conversation(conv["id"], user_id) is True
    assert svc.get_messages(conv["id"], user_id) == []


def test_message_artifacts_are_persisted_and_restored(db, user_id):
    from services.chat import ChatService

    svc = ChatService(db)
    conv = svc.create_conversation(user_id)
    artifact = {
        "id": "market-1",
        "type": "market_snapshot",
        "version": 1,
        "data": {"symbol": "AAPL", "quote": {"price": 200}},
    }
    svc.add_message(conv["id"], "assistant", "Analysis", artifacts=[artifact])

    assert svc.get_messages(conv["id"], user_id)[0]["artifacts"] == [artifact]


def test_message_image_attachments_are_persisted_in_order(db, user_id, tmp_path):
    from services.chat import ChatService

    first = _add_image_asset(db, user_id, tmp_path, "first")
    second = _add_image_asset(db, user_id, tmp_path, "second")
    svc = ChatService(db)
    conv = svc.create_conversation(user_id)

    svc.add_message(
        conv["id"], "user", "analyze",
        attachment_ids=[second.id, first.id], user_id=user_id,
    )

    message = svc.get_messages(conv["id"], user_id)[0]
    assert [item["id"] for item in message["attachments"]] == [second.id, first.id]
    assert message["attachments"][0]["url"] == f"/api/uploads/{second.id}"


def test_attachment_validation_is_user_scoped(db, user_id, tmp_path):
    import uuid as _uuid
    from datetime import datetime, timezone
    from models import User
    from services.chat import ChatService

    other_id = str(_uuid.uuid4())
    db.add(User(
        id=other_id, email="image-owner@test.local", password="x", name="Other",
        created_at=datetime.now(timezone.utc).isoformat(),
    ))
    db.flush()
    asset = _add_image_asset(db, other_id, tmp_path, "private")

    with pytest.raises(ValueError, match="invalid_attachments"):
        ChatService(db).validate_attachment_ids(user_id, [asset.id])


def test_model_history_includes_only_four_most_recent_images(db, user_id, tmp_path):
    from services.chat import ChatService

    svc = ChatService(db)
    conv = svc.create_conversation(user_id)
    assets = [_add_image_asset(db, user_id, tmp_path, f"chart-{index}") for index in range(5)]
    for index, asset in enumerate(assets):
        svc.add_message(
            conv["id"], "user", f"chart {index}",
            attachment_ids=[asset.id], user_id=user_id,
        )

    history = svc._model_history(conv["id"])
    image_messages = [item for item in history if isinstance(item["content"], list)]
    image_parts = [
        part
        for item in image_messages
        for part in item["content"]
        if part["type"] == "input_image"
    ]

    assert len(image_parts) == 4
    assert history[0]["content"] == "chart 0"
    assert image_parts[-1]["detail"] == "high"
    assert image_parts[-1]["image_url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_send_message_runs_tools_and_persists(chat_service, db, user_id):
    from services.journal import JournalService
    JournalService(db).create_trade(
        symbol="BTCUSD", direction="long", pnl=250.0,
        open_time="2026-01-01T00:00:00Z", close_time="2026-01-01T01:00:00Z", user_id=user_id,
    )
    svc = chat_service
    conv = svc.create_conversation(user_id)

    chunks = []
    async for c in svc.send_message(conv["id"], user_id, "我赚了多少?", lang="zh"):
        chunks.append(c)
    answer = "".join(chunk for chunk in chunks if isinstance(chunk, str))
    assert "250.0" in answer

    event_types = [chunk.get("type") for chunk in chunks if isinstance(chunk, dict)]
    assert event_types[0] == "work_start"
    assert "work_item" in event_types
    assert event_types[-1] == "work_end"

    msgs = svc.get_messages(conv["id"], user_id)
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["content"] == answer
    assert msgs[1]["work"]["status"] == "completed"
    assert msgs[1]["work"]["duration_ms"] >= 0
    tool = msgs[1]["work"]["items"][0]
    assert tool["tool_name"] == "get_journal_stats"
    assert tool["status"] == "completed"
    assert "250.0" in tool["output"]
    assert all(m["id"] and m["created_at"] for m in msgs)


@pytest.mark.asyncio
async def test_market_command_streams_and_persists_artifact(db, user_id, monkeypatch):
    from services.agent import _DemoModel
    from services.chat import ChatService

    monkeypatch.setattr("services.agent.create_model", lambda: _DemoModel())
    monkeypatch.setattr(
        "services.market_research.get_market_snapshot",
        lambda asset_class, symbol, interval: {
            "provider": "test",
            "asset_class": asset_class,
            "symbol": symbol,
            "interval": interval,
            "quote": {"price": 200},
            "technicals": {},
            "recent_candles": [],
            "warnings": [],
        },
    )
    service = ChatService(db)
    conversation = service.create_conversation(user_id)

    chunks = []
    async for chunk in service.send_message(
        conversation["id"], user_id, "/stock AAPL 1day",
    ):
        chunks.append(chunk)

    artifacts = [
        chunk["artifact"] for chunk in chunks
        if isinstance(chunk, dict) and chunk.get("type") == "artifact"
    ]
    assert len(artifacts) == 1
    assert artifacts[0]["type"] == "market_snapshot"
    assert artifacts[0]["data"]["quote"]["price"] == 200
    saved = service.get_messages(conversation["id"], user_id)[-1]
    assert saved["artifacts"] == artifacts
    assert [item["tool_name"] for item in saved["work"]["items"]] == [
        "get_stock_market_data",
    ]


@pytest.mark.asyncio
async def test_check_command_streams_opportunity_artifact(db, user_id, monkeypatch):
    from services.agent import _DemoModel
    from services.chat import ChatService
    from services.journal import JournalService

    monkeypatch.setattr("services.agent.create_model", lambda: _DemoModel())
    monkeypatch.setattr(
        "services.market_research.get_market_snapshot",
        lambda asset_class, symbol, interval: {
            "provider": "test", "asset_class": asset_class, "symbol": symbol,
            "interval": interval, "quote": {"price": 102}, "technicals": {},
            "recent_candles": [], "warnings": [],
        },
    )
    JournalService(db).create_rule(
        user_id, "Need stop", "require_stop_loss", None, "critical",
    )
    service = ChatService(db)
    conversation = service.create_conversation(user_id)

    chunks = []
    async for chunk in service.send_message(
        conversation["id"], user_id,
        "/check stock AAPL long entry=100 stop=95 target=110 quantity=2 account=1000",
    ):
        chunks.append(chunk)

    artifact = next(
        chunk["artifact"] for chunk in chunks
        if isinstance(chunk, dict) and chunk.get("type") == "artifact"
    )
    assert artifact["type"] == "opportunity_check"
    assert artifact["data"]["verdict"] == "compliant"
    assert artifact["data"]["compliance"]["passed"] == 1


def test_replace_last_user_turn_removes_previous_answer(db, user_id):
    from services.chat import ChatService

    svc = ChatService(db)
    conv = svc.create_conversation(user_id)
    svc.add_message(conv["id"], "user", "first question")
    svc.add_message(conv["id"], "assistant", "first answer")
    svc.add_message(conv["id"], "user", "old final question")
    svc.add_message(conv["id"], "assistant", "old final answer")

    assert svc.replace_last_user_turn(conv["id"], user_id, "edited final question") is True

    msgs = svc.get_messages(conv["id"], user_id)
    assert [(m["role"], m["content"]) for m in msgs] == [
        ("user", "first question"),
        ("assistant", "first answer"),
        ("user", "edited final question"),
    ]


def test_replace_last_user_turn_preserves_attachments(db, user_id, tmp_path):
    from services.chat import ChatService

    svc = ChatService(db)
    conv = svc.create_conversation(user_id)
    asset = _add_image_asset(db, user_id, tmp_path, "replace")
    svc.add_message(
        conv["id"], "user", "old question",
        attachment_ids=[asset.id], user_id=user_id,
    )
    svc.add_message(conv["id"], "assistant", "old answer")

    assert svc.replace_last_user_turn(conv["id"], user_id, "new question") is True

    message = svc.get_messages(conv["id"], user_id)[0]
    assert message["content"] == "new question"
    assert [item["id"] for item in message["attachments"]] == [asset.id]


def test_replace_only_user_message_updates_conversation_title(db, user_id):
    from services.chat import ChatService

    svc = ChatService(db)
    conv = svc.create_conversation(user_id)
    svc.add_message(conv["id"], "user", "old title")
    svc.add_message(conv["id"], "assistant", "old answer")

    assert svc.replace_last_user_turn(conv["id"], user_id, "new title") is True
    assert svc.get_conversation(conv["id"], user_id)["title"] == "new title"


def test_first_message_sets_title(db, user_id):
    from services.chat import ChatService
    svc = ChatService(db)
    conv = svc.create_conversation(user_id)
    svc.add_message(conv["id"], "user", "这是我的第一个问题它会变成标题吗")
    title = svc.get_conversation(conv["id"], user_id)["title"]
    assert title.startswith("这是我的第一个问题")
    assert len(title) <= 30


def test_pending_state_columns_exist(db):
    from sqlalchemy import inspect
    cols = {c["name"] for c in inspect(db.bind).get_columns("chat_conversations")}
    assert {"pending_state", "pending_at", "pinned_at", "pinned_order", "sort_order"} <= cols
    message_cols = {c["name"] for c in inspect(db.bind).get_columns("chat_messages")}
    assert "artifacts" in message_cols


def test_message_page_returns_latest_rows_with_cursor_metadata(db, user_id):
    from services.chat import ChatService

    svc = ChatService(db)
    conv = svc.create_conversation(user_id)
    for index in range(5):
        svc.add_message(conv["id"], "user" if index % 2 == 0 else "assistant", str(index))

    first = svc.get_message_page(conv["id"], user_id, limit=2, offset=0)
    second = svc.get_message_page(conv["id"], user_id, limit=2, offset=2)

    assert first is not None and second is not None
    assert [message["content"] for message in first["messages"]] == ["3", "4"]
    assert first["page"] == {
        "limit": 2, "offset": 0, "has_more": True, "next_offset": 2,
    }
    assert [message["content"] for message in second["messages"]] == ["1", "2"]


def test_model_history_is_bounded_and_keeps_latest_turns(db, user_id):
    from services.chat import ChatService, _MODEL_HISTORY_MAX_MESSAGES

    svc = ChatService(db)
    conv = svc.create_conversation(user_id)
    for index in range(_MODEL_HISTORY_MAX_MESSAGES + 25):
        svc.add_message(conv["id"], "user" if index % 2 == 0 else "assistant", f"message-{index}")

    history = svc._model_history(conv["id"])

    assert len(history) == _MODEL_HISTORY_MAX_MESSAGES
    assert history[-1]["content"] == f"message-{_MODEL_HISTORY_MAX_MESSAGES + 24}"
    assert history[0]["content"] == "message-25"


def test_model_history_respects_token_budget(db, user_id):
    from services.chat import ChatService, _MODEL_HISTORY_TOKEN_BUDGET, _estimate_tokens

    svc = ChatService(db)
    conv = svc.create_conversation(user_id)
    for index in range(10):
        svc.add_message(conv["id"], "user", f"{index}-" + ("中" * 6000))

    history = svc._model_history(conv["id"])
    estimated = sum(_estimate_tokens(message["content"]) for message in history)

    assert estimated <= _MODEL_HISTORY_TOKEN_BUDGET
    assert history[-1]["content"].startswith("9-")
    assert len(history) < 10

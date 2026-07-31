import json

from services.action_enrich import enrich_interruption
from services.journal import JournalService
from services.memory import AssistantMemoryService


class _FakeItem:
    """Mimics an Agents SDK ToolApprovalItem for enrich input."""

    def __init__(self, name, call_id, arguments):
        self.name = name

        class _Raw:
            pass

        self.raw_item = _Raw()
        self.raw_item.call_id = call_id
        self.raw_item.arguments = arguments


def test_enrich_delete_trades_previews_rows(db, user_id):
    t1 = JournalService(db).create_trade(
        symbol="XAUUSD",
        direction="long",
        pnl=120.5,
        open_time="2026-06-01T00:00:00Z",
        close_time="2026-06-01T01:00:00Z",
        user_id=user_id,
    )
    item = _FakeItem("delete_trades", "call_1", json.dumps({"trade_ids": [t1["id"]]}))

    out = enrich_interruption(db, user_id, item, lang="zh")

    assert out["action"] == "delete"
    assert out["entity"] == "trade"
    assert out["call_id"] == "call_1"
    assert "1" in out["title"]
    assert any("XAUUSD" in p["label"] for p in out["preview"])


def test_enrich_create_portfolio_uses_args(db, user_id):
    item = _FakeItem("create_portfolio", "call_2", json.dumps({"name": "Main", "currency": "USD"}))

    out = enrich_interruption(db, user_id, item, lang="en")

    assert out["action"] == "create"
    assert out["entity"] == "portfolio"
    assert any("Main" in p["label"] for p in out["preview"])


def test_enrich_memory_actions_show_readable_preview(db, user_id):
    remembered = _FakeItem("remember_memory", "call_3", json.dumps({
        "content": "I avoid holding positions overnight.",
    }))

    created = enrich_interruption(db, user_id, remembered, lang="en")

    assert created["entity"] == "memory"
    assert "Save" in created["title"]
    assert created["preview"] == [{"label": "I avoid holding positions overnight.", "sub": ""}]

    memory = AssistantMemoryService(db).create_memory(user_id, "I avoid holding positions overnight.")
    forgotten = _FakeItem("forget_memories", "call_4", json.dumps({"memory_ids": [memory["id"]]}))

    deleted = enrich_interruption(db, user_id, forgotten, lang="en")

    assert deleted["entity"] == "memory"
    assert "1" in deleted["title"]
    assert deleted["preview"] == [{"label": "I avoid holding positions overnight.", "sub": ""}]


def test_enrich_unknown_tool_is_generic(db, user_id):
    item = _FakeItem("mystery_tool", "call_3", "{}")

    out = enrich_interruption(db, user_id, item, lang="en")

    assert out["action"] == "update"
    assert out["call_id"] == "call_3"


def test_enrich_create_and_update_show_every_mutated_field(db, user_id):
    created = enrich_interruption(
        db,
        user_id,
        _FakeItem("create_trade", "call_create", json.dumps({
            "symbol": "NQ", "direction": "long", "pnl": -125.5,
            "tags": ["breakout"], "notes": "late entry",
        })),
        lang="en",
    )
    updated = enrich_interruption(
        db,
        user_id,
        _FakeItem("update_entry", "call_update", json.dumps({
            "entry_id": "entry-1", "amount": 25000, "notes": "broker statement",
        })),
        lang="en",
    )

    created_text = "\n".join(line["label"] for line in created["preview"])
    updated_text = "\n".join(line["label"] for line in updated["preview"])
    assert all(field in created_text for field in ("NQ", "long", "-125.5", "breakout", "late entry"))
    assert all(field in updated_text for field in ("entry-1", "25000", "broker statement"))

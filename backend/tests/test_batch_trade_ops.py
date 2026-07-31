from datetime import datetime, timezone

import pytest

from models import User
from services.journal import JournalService


USER_A = "user-a"
USER_B = "user-b"


@pytest.fixture
def svc(db):
    now = datetime.now(timezone.utc).isoformat()
    for uid, email in [(USER_A, "a@x"), (USER_B, "b@x")]:
        db.add(User(id=uid, email=email, password="x", name="", created_at=now))
    db.flush()
    return JournalService(db)


def _mk(svc, user_id, symbol, direction="long", tags=None, open_time="2026-01-10T00:00:00Z"):
    return svc.create_trade(
        symbol=symbol, direction=direction, open_time=open_time,
        tags=tags or [], user_id=user_id,
    )


# ── resolve_trade_ids_by_filter ─────────────────────────────

def test_resolve_no_filter_returns_all_for_user(svc):
    t1 = _mk(svc, USER_A, "BTCUSD")
    t2 = _mk(svc, USER_A, "ETHUSD")
    _mk(svc, USER_B, "XAUUSD")

    ids = svc.resolve_trade_ids_by_filter(USER_A)
    assert set(ids) == {t1["id"], t2["id"]}


def test_resolve_by_symbol(svc):
    t1 = _mk(svc, USER_A, "BTCUSD")
    _mk(svc, USER_A, "ETHUSD")

    ids = svc.resolve_trade_ids_by_filter(USER_A, symbol="BTC")
    assert ids == [t1["id"]]


def test_resolve_by_direction(svc):
    _mk(svc, USER_A, "BTCUSD", direction="long")
    t2 = _mk(svc, USER_A, "BTCUSD", direction="short")

    ids = svc.resolve_trade_ids_by_filter(USER_A, direction="short")
    assert ids == [t2["id"]]


def test_resolve_is_cross_user_isolated(svc):
    _mk(svc, USER_A, "BTCUSD")
    t2 = _mk(svc, USER_B, "BTCUSD")

    ids = svc.resolve_trade_ids_by_filter(USER_B)
    assert ids == [t2["id"]]


# ── batch_delete_trades ─────────────────────────────────────

def test_batch_delete_removes_rows_returns_count(svc):
    t1 = _mk(svc, USER_A, "BTCUSD")
    t2 = _mk(svc, USER_A, "ETHUSD")
    t3 = _mk(svc, USER_A, "XAUUSD")

    n = svc.batch_delete_trades([t1["id"], t2["id"]], user_id=USER_A)
    assert n == 2

    remaining = svc.list_trades(user_id=USER_A)
    assert [r["id"] for r in remaining] == [t3["id"]]


def test_batch_delete_empty_list_is_noop(svc):
    _mk(svc, USER_A, "BTCUSD")
    assert svc.batch_delete_trades([], user_id=USER_A) == 0


def test_batch_delete_cross_user_ids_are_filtered(svc):
    mine = _mk(svc, USER_A, "BTCUSD")
    theirs = _mk(svc, USER_B, "ETHUSD")

    n = svc.batch_delete_trades([mine["id"], theirs["id"]], user_id=USER_A)
    assert n == 1
    # Their row still exists
    assert svc.get_trade(theirs["id"], user_id=USER_B) is not None


def test_batch_delete_nonexistent_ids_silently_skip(svc):
    real = _mk(svc, USER_A, "BTCUSD")
    n = svc.batch_delete_trades([real["id"], "fake-id-1", "fake-id-2"], user_id=USER_A)
    assert n == 1


# ── batch_add_tags ──────────────────────────────────────────

def test_batch_add_tags_preserves_order_and_dedups(svc):
    t = _mk(svc, USER_A, "BTCUSD", tags=["a", "b"])

    n = svc.batch_add_tags([t["id"]], user_id=USER_A, tags=["b", "c"])
    assert n == 1

    fetched = svc.get_trade(t["id"], user_id=USER_A)
    assert fetched["tags"] == ["a", "b", "c"]


def test_batch_add_tags_to_empty_tags(svc):
    t = _mk(svc, USER_A, "BTCUSD", tags=[])

    svc.batch_add_tags([t["id"]], user_id=USER_A, tags=["x", "y"])

    fetched = svc.get_trade(t["id"], user_id=USER_A)
    assert fetched["tags"] == ["x", "y"]


def test_batch_add_tags_cross_user_isolation(svc):
    mine = _mk(svc, USER_A, "BTCUSD", tags=["orig"])
    theirs = _mk(svc, USER_B, "ETHUSD", tags=["orig"])

    n = svc.batch_add_tags([mine["id"], theirs["id"]], user_id=USER_A, tags=["added"])
    assert n == 1
    assert svc.get_trade(mine["id"], user_id=USER_A)["tags"] == ["orig", "added"]
    # Their row unchanged
    assert svc.get_trade(theirs["id"], user_id=USER_B)["tags"] == ["orig"]


def test_batch_add_tags_multi_trade_rowcount(svc):
    t1 = _mk(svc, USER_A, "BTCUSD", tags=[])
    t2 = _mk(svc, USER_A, "ETHUSD", tags=["existing"])

    n = svc.batch_add_tags([t1["id"], t2["id"]], user_id=USER_A, tags=["new"])
    assert n == 2
    assert svc.get_trade(t1["id"], user_id=USER_A)["tags"] == ["new"]
    assert svc.get_trade(t2["id"], user_id=USER_A)["tags"] == ["existing", "new"]


def test_batch_add_tags_empty_ids_is_noop(svc):
    assert svc.batch_add_tags([], user_id=USER_A, tags=["x"]) == 0

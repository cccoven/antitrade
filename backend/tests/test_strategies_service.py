import time

import pytest
from models import Trade
from services.strategies import StrategyService


@pytest.fixture
def svc(db, user_id):
    """StrategyService backed by the transactional test Session."""
    return StrategyService(db), user_id


@pytest.fixture
def svc2(db):
    """A second user for isolation tests."""
    import uuid
    from datetime import datetime, timezone
    from models import User
    uid = str(uuid.uuid4())
    db.add(User(id=uid, email=f"{uid}@t2.test", password="x", name="T2",
                created_at=datetime.now(timezone.utc).isoformat()))
    db.flush()
    return uid


def test_create_returns_full_object_with_defaults(svc):
    service, uid = svc
    s = service.create_strategy(user_id=uid)
    assert s["id"]
    assert s["user_id"] == uid
    assert s["title"] == ""
    assert s["body"] == ""
    assert s["tags"] == []
    assert s["trade_count"] == 0
    assert s["win_rate"] is None
    assert s["created_at"] == s["updated_at"]


def test_create_with_fields(svc):
    service, uid = svc
    s = service.create_strategy(user_id=uid, title="High 2", body="setup notes", tags=["xau", "intraday"])
    assert s["title"] == "High 2"
    assert s["body"] == "setup notes"
    assert s["tags"] == ["xau", "intraday"]


def test_get_returns_none_for_other_users_strategy(svc, svc2):
    service, uid = svc
    uid2 = svc2
    s = service.create_strategy(user_id=uid, title="mine")
    assert service.get_strategy(user_id=uid2, strategy_id=s["id"]) is None
    assert service.get_strategy(user_id=uid, strategy_id=s["id"])["id"] == s["id"]


def test_list_returns_full_objects_ordered_by_updated_at_desc(svc):
    service, uid = svc
    a = service.create_strategy(user_id=uid, title="A")
    time.sleep(0.01)
    b = service.create_strategy(user_id=uid, title="B")
    rows = service.list_strategies(user_id=uid)
    assert [r["id"] for r in rows] == [b["id"], a["id"]]
    assert "body" in rows[0] and "tags" in rows[0]


def test_list_isolates_by_user(svc, svc2):
    service, uid = svc
    uid2 = svc2
    service.create_strategy(user_id=uid, title="A")
    service.create_strategy(user_id=uid2, title="B")
    rows = service.list_strategies(user_id=uid)
    assert len(rows) == 1 and rows[0]["title"] == "A"


def test_list_includes_win_rate_from_scored_linked_trades(svc, svc2):
    service, uid = svc
    strategy = service.create_strategy(user_id=uid, title="Measured")
    now = "2026-07-24T00:00:00+00:00"

    def trade(trade_id: str, user_id: str, pnl: float | None) -> Trade:
        return Trade(
            id=trade_id,
            user_id=user_id,
            symbol="AAPL",
            direction="long",
            position_status="closed" if pnl is not None else "open",
            pnl=pnl,
            strategy_id=strategy["id"],
            created_at=now,
            updated_at=now,
        )

    service.session.add_all([
        trade("win", uid, 10),
        trade("loss", uid, -5),
        trade("breakeven", uid, 0),
        trade("unscored", uid, None),
        trade("other-user", svc2, 20),
    ])
    service.session.flush()

    listed = service.list_strategies(user_id=uid)[0]
    assert listed["trade_count"] == 3
    assert listed["win_rate"] == pytest.approx(100 / 3)

    detail = service.get_strategy(user_id=uid, strategy_id=strategy["id"])
    assert detail is not None
    assert detail["trade_count"] == 3
    assert detail["win_rate"] == pytest.approx(100 / 3)


def test_patch_updates_only_provided_fields(svc):
    service, uid = svc
    s = service.create_strategy(user_id=uid, title="x", body="orig", tags=["t1"])
    time.sleep(0.01)
    updated = service.patch_strategy(user_id=uid, strategy_id=s["id"], title="renamed")
    assert updated["title"] == "renamed"
    assert updated["body"] == "orig"
    assert updated["tags"] == ["t1"]
    assert updated["updated_at"] > s["updated_at"]


def test_patch_returns_none_for_other_user(svc, svc2):
    service, uid = svc
    uid2 = svc2
    s = service.create_strategy(user_id=uid, title="x")
    assert service.patch_strategy(user_id=uid2, strategy_id=s["id"], title="hack") is None


def test_delete_returns_true_when_owned(svc):
    service, uid = svc
    s = service.create_strategy(user_id=uid, title="x")
    assert service.delete_strategy(user_id=uid, strategy_id=s["id"]) is True
    assert service.get_strategy(user_id=uid, strategy_id=s["id"]) is None


def test_delete_returns_false_for_other_user(svc, svc2):
    service, uid = svc
    uid2 = svc2
    s = service.create_strategy(user_id=uid, title="x")
    assert service.delete_strategy(user_id=uid2, strategy_id=s["id"]) is False
    assert service.get_strategy(user_id=uid, strategy_id=s["id"]) is not None


def test_list_options_returns_only_id_and_title(svc):
    service, uid = svc
    service.create_strategy(user_id=uid, title="One", body="long body", tags=["t"])
    opts = service.list_strategy_options(user_id=uid)
    assert opts == [{"id": opts[0]["id"], "title": "One"}]

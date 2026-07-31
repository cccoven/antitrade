from datetime import datetime, timezone

import pandas as pd
import pytest

from models import User
from services.backtest import BacktestService
from services.market_gateway import MarketDataError


USER_ID = "test-user"


@pytest.fixture
def svc(db):
    now = datetime.now(timezone.utc).isoformat()
    for uid, email in [(USER_ID, "a@x"), ("alice", "alice@x"), ("bob", "bob@x")]:
        db.add(User(id=uid, email=email, password="x", name="", created_at=now))
    db.flush()
    return BacktestService(db)


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
    "exit_conditions": [
        {
            "left": {"type": "ema", "params": {"period": 10}},
            "operator": "cross_below",
            "right": {"type": "ema", "params": {"period": 20}},
        }
    ],
}


# ------------------------------------------------------------------
# Strategy CRUD
# ------------------------------------------------------------------


def test_create_strategy(svc):
    strategy = svc.create_strategy(USER_ID, "My Strategy", SAMPLE_CONFIG)

    assert strategy["id"]
    assert strategy["user_id"] == USER_ID
    assert strategy["name"] == "My Strategy"
    assert strategy["config"]["schema_version"] == 2
    assert strategy["config"]["entry_groups"][0]["operator"] == "and"
    assert strategy["config"]["series_id"] == "series:spot:xau-usd:consolidated"
    assert strategy["config"]["stop_loss_pct"] == 2.0
    assert strategy["config"]["take_profit_pct"] == 4.0
    assert strategy["created_at"]
    assert strategy["updated_at"]


def test_list_strategies(svc):
    svc.create_strategy(USER_ID, "Strategy A", {"symbol": "XAUUSD"})
    svc.create_strategy(USER_ID, "Strategy B", {"symbol": "BTCUSD"})

    strategies = svc.list_strategies(USER_ID)
    assert len(strategies) == 2
    names = {s["name"] for s in strategies}
    assert names == {"Strategy A", "Strategy B"}


def test_get_strategy(svc):
    created = svc.create_strategy(USER_ID, "Test", SAMPLE_CONFIG)
    fetched = svc.get_strategy(USER_ID, created["id"])

    assert fetched is not None
    assert fetched["id"] == created["id"]
    assert fetched["config"]["series_id"] == "series:spot:xau-usd:consolidated"


def test_get_strategy_not_found(svc):
    assert svc.get_strategy(USER_ID, "nonexistent-id") is None


def test_update_strategy_name(svc):
    created = svc.create_strategy(USER_ID, "Old Name", SAMPLE_CONFIG)
    updated = svc.update_strategy(USER_ID, created["id"], name="New Name")

    assert updated is not None
    assert updated["name"] == "New Name"
    assert updated["config"]["series_id"] == "series:spot:xau-usd:consolidated"
    assert updated["updated_at"] >= created["updated_at"]


def test_update_strategy_config(svc):
    created = svc.create_strategy(USER_ID, "Test", {"symbol": "XAUUSD"})
    new_config = {"symbol": "BTCUSD", "interval": "60"}
    updated = svc.update_strategy(USER_ID, created["id"], config=new_config)

    assert updated is not None
    assert updated["config"]["symbol"] == "BTCUSD"
    assert updated["config"]["interval"] == "60"
    assert updated["config"]["schema_version"] == 2
    assert updated["config"]["series_id"] == "series:crypto:btc-usd:consolidated"


def test_create_strategy_rejects_unknown_series_id(svc):
    with pytest.raises(ValueError, match="Unknown market series"):
        svc.create_strategy(
            USER_ID,
            "Invalid",
            {"symbol": "XAUUSD", "series_id": "series:missing"},
        )


def test_create_strategy_rejects_invalid_config_before_run(svc):
    with pytest.raises(ValueError, match="position_size"):
        svc.create_strategy(
            USER_ID,
            "Invalid",
            {"symbol": "XAUUSD", "position_size": -1},
        )


def test_filter_date_range_includes_entire_end_date():
    frame = pd.DataFrame(
        {"close": [1.0, 2.0, 3.0]},
        index=pd.DatetimeIndex(
            [
                "2026-07-24T00:00:00Z",
                "2026-07-24T16:00:00Z",
                "2026-07-25T00:00:00Z",
            ],
        ),
    )

    filtered = BacktestService._filter_date_range(
        frame,
        "2026-07-24",
        "2026-07-24",
    )

    assert list(filtered["close"]) == [1.0, 2.0]


@pytest.mark.parametrize(
    ("timeframe", "expected"),
    [
        ("5", "2026-07-24T12:30:00+00:00"),
        ("60", "2026-07-24T12:00:00+00:00"),
        ("D", "2026-07-24T00:00:00+00:00"),
    ],
)
def test_backtest_query_end_aligns_to_stable_bar_boundary(
    timeframe,
    expected,
):
    aligned = BacktestService._align_to_timeframe(
        datetime(2026, 7, 24, 12, 34, 56, tzinfo=timezone.utc),
        timeframe,
    )

    assert aligned.isoformat() == expected


def test_public_backtest_error_hides_provider_details():
    error = MarketDataError(
        "market_data_unavailable",
        "yahoo:timeout, tradingview:authentication_failed",
    )

    assert BacktestService._public_error(error) == (
        "Market data is temporarily unavailable"
    )


def test_update_strategy_not_found(svc):
    assert svc.update_strategy(USER_ID, "nonexistent-id", name="X") is None


def test_delete_strategy(svc):
    created = svc.create_strategy(USER_ID, "Test", SAMPLE_CONFIG)
    assert svc.delete_strategy(USER_ID, created["id"]) is True
    assert svc.get_strategy(USER_ID, created["id"]) is None


def test_delete_strategy_not_found(svc):
    assert svc.delete_strategy(USER_ID, "nonexistent-id") is False


def test_user_isolation(svc):
    """Strategies created by one user must not be visible to another."""
    alice_strategy = svc.create_strategy("alice", "Alice Strat", {"symbol": "XAUUSD"})
    svc.create_strategy("bob", "Bob Strat", {"symbol": "BTCUSD"})

    alice_list = svc.list_strategies("alice")
    bob_list = svc.list_strategies("bob")

    assert len(alice_list) == 1
    assert alice_list[0]["name"] == "Alice Strat"
    assert len(bob_list) == 1
    assert bob_list[0]["name"] == "Bob Strat"

    # Alice can't access Bob's strategy
    assert svc.get_strategy("alice", bob_list[0]["id"]) is None
    assert svc.update_strategy("alice", bob_list[0]["id"], name="Hacked") is None
    assert svc.delete_strategy("alice", bob_list[0]["id"]) is False

    # Bob's strategy still exists
    assert svc.get_strategy("bob", bob_list[0]["id"]) is not None

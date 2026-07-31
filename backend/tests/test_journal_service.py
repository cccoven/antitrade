import uuid
from datetime import datetime, timezone

import pytest

from models import Strategy, User
from services.journal import JournalService


USER_ID = "test-user"


@pytest.fixture
def svc(db):
    # Seed required users
    now = datetime.now(timezone.utc).isoformat()
    for uid, email in [(USER_ID, "a@x"), ("alice", "alice@x"), ("bob", "bob@x")]:
        db.add(User(id=uid, email=email, password="x", name="", created_at=now))
    db.flush()
    return JournalService(db)


def test_create_and_get_trade(svc):
    trade = svc.create_trade(
        symbol="XAUUSD",
        direction="long",
        open_price=1900.50,
        quantity=1.0,
        open_time="2025-01-10T09:00:00Z",
        tags=["gold", "breakout"],
        notes="Test trade",
        user_id=USER_ID,
    )

    assert trade["id"]
    assert trade["symbol"] == "XAUUSD"
    assert trade["direction"] == "long"
    assert trade["position_status"] == "open"
    assert trade["open_price"] == 1900.50
    assert trade["quantity"] == 1.0
    assert trade["open_time"] == "2025-01-10T09:00:00Z"
    assert trade["tags"] == ["gold", "breakout"]
    assert trade["notes"] == "Test trade"
    assert trade["source"] == "manual"
    assert trade["fees"] == 0
    assert trade["created_at"]
    assert trade["updated_at"]

    fetched = svc.get_trade(trade["id"], user_id=USER_ID)
    assert fetched is not None
    assert fetched["id"] == trade["id"]
    assert fetched["symbol"] == "XAUUSD"
    assert fetched["tags"] == ["gold", "breakout"]


def test_trade_persists_canonical_market_series(svc):
    trade = svc.create_trade(
        symbol="XAUUSD",
        series_id="series:spot:xau-usd:consolidated",
        direction="long",
        user_id=USER_ID,
    )

    assert trade["series_id"] == "series:spot:xau-usd:consolidated"


def test_trade_rejects_unknown_canonical_market_series(svc):
    with pytest.raises(ValueError, match="unknown_market_series"):
        svc.create_trade(
            symbol="XAUUSD",
            series_id="series:missing",
            direction="long",
            user_id=USER_ID,
        )


def test_trade_plan_converts_and_persists_structured_review(svc):
    plan = svc.create_trade_plan(
        user_id=USER_ID,
        symbol="NQ",
        market="futures",
        direction="long",
        entry_price=100,
        target_price=110,
        stop_loss=95,
        account_size=10000,
        risk_percent=1,
        thesis="Breakout retest",
        strategy_id=None,
    )

    assert plan["risk_amount"] == pytest.approx(100)
    assert plan["quantity"] == pytest.approx(1)
    assert plan["risk_reward"] == pytest.approx(2)
    assert plan["series_id"] == "series:futures:nq:front"

    svc.create_rule(USER_ID, "Max 1%", "max_risk_percent", 1, "critical")
    svc.create_rule(USER_ID, "Need notes", "require_notes", None, "important")
    trade = svc.create_trade(
        user_id=USER_ID,
        symbol="NQ",
        direction="long",
        open_price=100,
        target_price=110,
        stop_loss=95,
        quantity=1,
        plan_id=plan["id"],
        notes="Breakout retest",
        setup_type="breakout",
        emotional_state="calm",
        mistakes=["early_exit"],
        confidence=8,
        execution_quality=7,
    )

    assert trade["setup_type"] == "breakout"
    assert trade["emotional_state"] == "calm"
    assert trade["mistakes"] == ["early_exit"]
    assert trade["confidence"] == 8
    assert trade["execution_quality"] == 7
    assert trade["compliance"]["score"] == 100
    assert svc.list_trade_plans(USER_ID, status="active") == []
    assert svc.list_trade_plans(USER_ID, status="converted")[0]["id"] == plan["id"]


def test_compliance_is_non_blocking_and_records_failures(svc):
    svc.create_rule(USER_ID, "Need stop", "require_stop_loss", None, "critical")
    svc.create_rule(USER_ID, "Confidence 7+", "min_confidence", 7, "important")

    preview = svc.evaluate_compliance(USER_ID, {"direction": "long", "confidence": 4})
    assert preview["failed"] == 2

    trade = svc.create_trade(
        user_id=USER_ID,
        symbol="ES",
        direction="long",
        confidence=4,
    )
    assert trade["id"]
    assert trade["compliance"]["failed"] == 2
    assert trade["compliance"]["score"] == 0


def test_list_trades_with_filters(svc):
    svc.create_trade(
        symbol="XAUUSD",
        direction="long",
        open_price=1900.0,
        open_time="2025-01-10T09:00:00Z",
        user_id=USER_ID,
    )
    svc.create_trade(
        symbol="BTCUSD",
        direction="short",
        open_price=42000.0,
        close_price=41000.0,
        pnl=1000.0,
        open_time="2025-01-11T10:00:00Z",
        user_id=USER_ID,
    )

    all_trades = svc.list_trades(user_id=USER_ID)
    assert len(all_trades) == 2

    by_symbol = svc.list_trades(user_id=USER_ID, symbol="XAUUSD")
    assert len(by_symbol) == 1
    assert by_symbol[0]["symbol"] == "XAUUSD"

    by_direction = svc.list_trades(user_id=USER_ID, direction="short")
    assert len(by_direction) == 1
    assert by_direction[0]["symbol"] == "BTCUSD"

    open_trades = svc.list_trades(user_id=USER_ID, position_status="open")
    closed_trades = svc.list_trades(user_id=USER_ID, position_status="closed")
    assert [trade["symbol"] for trade in open_trades] == ["XAUUSD"]
    assert [trade["symbol"] for trade in closed_trades] == ["BTCUSD"]
    assert svc.count_trades(user_id=USER_ID, position_status="closed") == 1


def test_update_trade(svc):
    trade = svc.create_trade(
        symbol="XAUUSD",
        direction="long",
        open_price=1900.0,
        user_id=USER_ID,
    )

    updated = svc.update_trade(
        trade["id"],
        user_id=USER_ID,
        close_price=1950.0,
        pnl=50.0,
    )

    assert updated is not None
    assert updated["close_price"] == 1950.0
    assert updated["pnl"] == 50.0
    assert updated["position_status"] == "closed"
    assert updated["updated_at"] >= trade["updated_at"]

    reopened = svc.update_trade(
        trade["id"],
        user_id=USER_ID,
        position_status="open",
        close_price=None,
        close_time=None,
        pnl=None,
    )
    assert reopened["position_status"] == "open"


def test_delete_trade(svc):
    trade = svc.create_trade(
        symbol="XAUUSD",
        direction="long",
        open_price=1900.0,
        user_id=USER_ID,
    )

    result = svc.delete_trade(trade["id"], user_id=USER_ID)
    assert result is True

    fetched = svc.get_trade(trade["id"], user_id=USER_ID)
    assert fetched is None


def test_batch_create(svc):
    trades_data = [
        {"symbol": "XAUUSD", "direction": "long", "open_price": 1900.0},
        {"symbol": "BTCUSD", "direction": "short", "open_price": 42000.0},
    ]

    created = svc.batch_create_trades(trades_data, user_id=USER_ID)
    assert len(created) == 2
    assert created[0]["symbol"] == "XAUUSD"
    assert created[1]["symbol"] == "BTCUSD"

    all_trades = svc.list_trades(user_id=USER_ID)
    assert len(all_trades) == 2


def test_user_isolation(svc):
    """Trades created by one user must not be visible to another."""
    alice_trade = svc.create_trade(
        symbol="XAUUSD", direction="long", open_price=1900.0,
        user_id="alice",
    )
    bob_trade = svc.create_trade(
        symbol="BTCUSD", direction="short", open_price=42000.0,
        user_id="bob",
    )

    alice_trades = svc.list_trades(user_id="alice")
    bob_trades = svc.list_trades(user_id="bob")

    assert len(alice_trades) == 1
    assert alice_trades[0]["symbol"] == "XAUUSD"
    assert len(bob_trades) == 1
    assert bob_trades[0]["symbol"] == "BTCUSD"

    # Alice can't fetch, update, or delete Bob's trade
    assert svc.get_trade(bob_trade["id"], user_id="alice") is None
    assert svc.update_trade(bob_trade["id"], user_id="alice", pnl=999.0) is None
    assert svc.delete_trade(bob_trade["id"], user_id="alice") is False

    # Bob's trade is still there
    assert svc.get_trade(bob_trade["id"], user_id="bob") is not None


def test_compute_stats_basic(svc):
    """3 closed trades with known PnL => correct aggregated stats."""
    svc.create_trade(
        symbol="XAUUSD", direction="long",
        open_time="2025-01-10T09:00:00Z", close_time="2025-01-10T10:00:00Z",
        pnl=40.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="XAUUSD", direction="short",
        open_time="2025-01-11T09:00:00Z", close_time="2025-01-11T12:00:00Z",
        pnl=-500.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="XAUUSD", direction="long",
        open_time="2025-01-12T09:00:00Z", close_time="2025-01-12T09:30:00Z",
        pnl=50.0, user_id=USER_ID,
    )

    stats = svc.compute_stats(user_id=USER_ID)

    assert stats["total_trades"] == 3
    assert stats["total_pnl"] == pytest.approx(-410.0)
    assert stats["winners"] == 2
    assert stats["losers"] == 1
    assert stats["win_rate"] == pytest.approx(2 / 3)
    assert stats["profit_factor"] == pytest.approx(90.0 / 500.0)
    assert stats["max_consecutive_losses"] == 1
    assert len(stats["equity_curve"]) == 3
    assert stats["by_direction"] is not None
    assert stats["by_tag"] is not None


def test_compute_stats_by_symbol(svc):
    """2 trades on different symbols => by_symbol has both entries."""
    svc.create_trade(
        symbol="XAUUSD", direction="long",
        open_time="2025-01-10T09:00:00Z", close_time="2025-01-10T10:00:00Z",
        pnl=100.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="BTCUSD", direction="short",
        open_time="2025-01-11T09:00:00Z", close_time="2025-01-11T12:00:00Z",
        pnl=-30.0, user_id=USER_ID,
    )

    stats = svc.compute_stats(user_id=USER_ID)

    by_sym = {entry["symbol"]: entry for entry in stats["by_symbol"]}
    assert "XAUUSD" in by_sym
    assert "BTCUSD" in by_sym
    assert by_sym["XAUUSD"]["total_pnl"] == pytest.approx(100.0)
    assert by_sym["XAUUSD"]["count"] == 1
    assert by_sym["XAUUSD"]["win_rate"] == pytest.approx(1.0)
    assert by_sym["BTCUSD"]["total_pnl"] == pytest.approx(-30.0)
    assert by_sym["BTCUSD"]["count"] == 1
    assert by_sym["BTCUSD"]["win_rate"] == pytest.approx(0.0)


def test_compute_stats_excludes_equity_points_without_close_time(svc):
    svc.create_trade(
        symbol="XAUUSD", direction="long",
        open_time="2025-01-10T09:00:00Z", close_time="2025-01-10T10:00:00Z",
        pnl=100.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="XAUUSD", direction="short",
        open_time="2025-01-11T09:00:00Z", close_time=None,
        pnl=-25.0, user_id=USER_ID,
    )

    stats = svc.compute_stats(user_id=USER_ID)

    assert stats["total_trades"] == 2
    assert stats["total_pnl"] == pytest.approx(75.0)
    assert stats["equity_curve"] == [
        {"time": "2025-01-10T10:00:00Z", "equity": pytest.approx(100.0)},
        {"time": "2025-01-11T09:00:00Z", "equity": pytest.approx(75.0)},
    ]


def test_compute_calendar_summary_by_day_and_week(svc):
    svc.create_trade(
        symbol="XAUUSD", direction="long",
        open_time="2026-02-03T09:00:00Z", close_time="2026-02-03T10:00:00Z",
        pnl=10.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="BTCUSD", direction="short",
        open_time="2026-02-05T08:00:00Z", close_time="2026-02-05T09:00:00Z",
        pnl=-4.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="EURUSD", direction="long",
        open_time="2026-02-17T13:00:00Z", close_time="2026-02-17T15:00:00Z",
        pnl=7.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="USOIL", direction="long",
        open_time="2026-03-01T09:00:00Z", close_time="2026-03-01T10:00:00Z",
        pnl=99.0, user_id=USER_ID,
    )

    summary = svc.compute_calendar_summary("2026-02", user_id=USER_ID)

    assert summary["month"] == "2026-02"

    by_day = {entry["date"]: entry for entry in summary["days"]}
    assert by_day["2026-02-03"]["trade_count"] == 1
    assert by_day["2026-02-03"]["total_pnl"] == pytest.approx(10.0)
    assert by_day["2026-02-03"]["win_rate"] == pytest.approx(1.0)
    assert by_day["2026-02-05"]["trade_count"] == 1
    assert by_day["2026-02-05"]["total_pnl"] == pytest.approx(-4.0)
    assert by_day["2026-02-17"]["trade_count"] == 1
    assert "2026-03-01" not in by_day

    by_week = {entry["week_index"]: entry for entry in summary["weeks"]}
    assert by_week[1]["label"] == "Week 1"
    assert by_week[1]["trade_count"] == 2
    assert by_week[1]["active_days"] == 2
    assert by_week[1]["total_pnl"] == pytest.approx(6.0)
    assert by_week[1]["win_rate"] == pytest.approx(0.5)
    assert by_week[3]["trade_count"] == 1
    assert by_week[3]["active_days"] == 1
    assert by_week[3]["total_pnl"] == pytest.approx(7.0)


def test_compute_stats_risk_metrics(svc):
    """3 winners and 2 losers => correct avg_win, avg_loss, win_loss_ratio, sharpe_ratio."""
    # Winners: 100, 200, 150  => avg_win = 150
    # Losers:  -80, -120      => avg_loss = -100
    # win_loss_ratio = 150 / 100 = 1.5
    svc.create_trade(
        symbol="XAUUSD", direction="long",
        open_time="2025-01-10T09:00:00Z", close_time="2025-01-10T10:00:00Z",
        pnl=100.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="XAUUSD", direction="long",
        open_time="2025-01-11T09:00:00Z", close_time="2025-01-11T10:00:00Z",
        pnl=200.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="XAUUSD", direction="long",
        open_time="2025-01-12T09:00:00Z", close_time="2025-01-12T10:00:00Z",
        pnl=150.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="XAUUSD", direction="short",
        open_time="2025-01-13T09:00:00Z", close_time="2025-01-13T10:00:00Z",
        pnl=-80.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="XAUUSD", direction="short",
        open_time="2025-01-14T09:00:00Z", close_time="2025-01-14T10:00:00Z",
        pnl=-120.0, user_id=USER_ID,
    )

    stats = svc.compute_stats(user_id=USER_ID)

    assert stats["avg_win"] == pytest.approx(150.0)
    assert stats["avg_loss"] == pytest.approx(-100.0)
    assert stats["win_loss_ratio"] == pytest.approx(1.5)
    assert isinstance(stats["sharpe_ratio"], float)


def test_compute_stats_heatmap(svc):
    """2 trades at same hour/weekday => by_hour_weekday has correct structure."""
    # 2025-01-13 is a Monday (weekday=0), hour=9
    svc.create_trade(
        symbol="XAUUSD", direction="long",
        open_time="2025-01-13T09:00:00Z", close_time="2025-01-13T10:00:00Z",
        pnl=50.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="BTCUSD", direction="short",
        open_time="2025-01-13T09:30:00Z", close_time="2025-01-13T10:30:00Z",
        pnl=-20.0, user_id=USER_ID,
    )

    stats = svc.compute_stats(user_id=USER_ID)

    heatmap = stats["by_hour_weekday"]
    assert isinstance(heatmap, list)
    assert len(heatmap) == 1  # both trades in same weekday=0, hour=9 bucket

    entry = heatmap[0]
    assert entry["weekday"] == 0  # Monday
    assert entry["hour"] == 9
    assert entry["trades"] == 2
    assert entry["wins"] == 1


def test_compute_stats_risk_metrics_no_trades(svc):
    """No trades => all risk metric fields are 0 or empty."""
    stats = svc.compute_stats(user_id=USER_ID)

    assert stats["avg_win"] == 0.0
    assert stats["avg_loss"] == 0.0
    assert stats["win_loss_ratio"] == 0.0
    assert stats["sharpe_ratio"] == 0.0
    assert stats["by_hour_weekday"] == []


def test_create_trade_with_exchange(svc):
    trade = svc.create_trade(
        symbol="BTCUSDT",
        direction="long",
        exchange="BINANCE",
        open_price=42000.0,
        open_time="2026-01-01T00:00:00Z",
        user_id=USER_ID,
    )
    assert trade["exchange"] == "BINANCE"

    fetched = svc.get_trade(trade["id"], user_id=USER_ID)
    assert fetched["exchange"] == "BINANCE"


def test_create_trade_without_exchange_defaults_to_null(svc):
    trade = svc.create_trade(
        symbol="XAUUSD",
        direction="long",
        user_id=USER_ID,
    )
    assert trade["exchange"] is None


def test_compute_stats_scalar_aggregates(svc):
    """Counts, gross vs net, fees, profit/loss totals; strict win/loss/breakeven split."""
    svc.create_trade(
        symbol="MGC", direction="long",
        open_time="2025-01-10T09:00:00Z", close_time="2025-01-10T10:00:00Z",
        pnl=100.0, fees=2.0, quantity=2.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="MGC", direction="short",
        open_time="2025-01-11T09:00:00Z", close_time="2025-01-11T10:00:00Z",
        pnl=-50.0, fees=2.0, quantity=3.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="MGC", direction="long",
        open_time="2025-01-12T09:00:00Z", close_time="2025-01-12T10:00:00Z",
        pnl=0.0, fees=2.0, quantity=1.0, user_id=USER_ID,
    )

    stats = svc.compute_stats(user_id=USER_ID)

    assert stats["total_trades"] == 3
    assert stats["winners"] == 1
    assert stats["losers"] == 1           # strict pnl<0, breakeven excluded
    assert stats["breakeven_trades"] == 1
    assert stats["total_contracts"] == pytest.approx(6.0)
    assert stats["winning_contracts"] == pytest.approx(2.0)
    assert stats["losing_contracts"] == pytest.approx(3.0)
    assert stats["total_pnl"] == pytest.approx(50.0)
    assert stats["gross_total_pnl"] == pytest.approx(50.0 + 6.0)  # +fees
    assert stats["total_fees"] == pytest.approx(6.0)
    assert stats["total_profit"] == pytest.approx(100.0)
    assert stats["total_loss"] == pytest.approx(-50.0)


def test_max_consecutive_losses_excludes_breakeven(svc):
    """A breakeven trade breaks a losing streak (strict pnl < 0 convention)."""
    # Sequence: loss, loss, breakeven, loss, loss, loss
    # Old behavior (<=0): max streak = 6
    # New behavior (<0):  max streak = 3  (the trailing run of three losses)
    pnls = [-10.0, -20.0, 0.0, -5.0, -15.0, -25.0]
    for i, p in enumerate(pnls):
        svc.create_trade(
            symbol="MGC", direction="long",
            open_time=f"2025-06-{i+1:02d}T09:00:00Z",
            close_time=f"2025-06-{i+1:02d}T10:00:00Z",
            pnl=p, user_id=USER_ID,
        )

    stats = svc.compute_stats(user_id=USER_ID)

    assert stats["max_consecutive_losses"] == 3


def test_compute_stats_largest_stdev_expectancy(svc):
    """Largest win/loss, sample stdev (n-1), and expectancy = gross/trades."""
    import statistics
    wins = [100.0, 200.0, 300.0]
    losses = [-50.0, -150.0]
    for i, p in enumerate(wins):
        svc.create_trade(
            symbol="MGC", direction="long",
            open_time=f"2025-02-{i+1:02d}T09:00:00Z",
            close_time=f"2025-02-{i+1:02d}T10:00:00Z",
            pnl=p, fees=1.0, user_id=USER_ID,
        )
    for j, p in enumerate(losses):
        svc.create_trade(
            symbol="MGC", direction="short",
            open_time=f"2025-02-{j+10:02d}T09:00:00Z",
            close_time=f"2025-02-{j+10:02d}T10:00:00Z",
            pnl=p, fees=1.0, user_id=USER_ID,
        )

    stats = svc.compute_stats(user_id=USER_ID)

    assert stats["largest_winner"] == pytest.approx(300.0)
    assert stats["largest_loser"] == pytest.approx(-150.0)
    assert stats["std_winner"] == pytest.approx(statistics.stdev(wins))
    assert stats["std_loser"] == pytest.approx(statistics.stdev(losses))
    # gross = (100+200+300-50-150) + 5 fees = 400 + 5 = 405
    # expectancy = 405 / 5 = 81.0
    assert stats["expectancy"] == pytest.approx(81.0)


def test_compute_stats_holding_time_breakdown(svc):
    """Avg + longest holding time overall and per outcome (seconds).
    Breakeven trade contributes to overall but NOT to winner/loser buckets."""
    # winners: 60s, 180s  -> avg=120, longest=180
    # losers:  90s         -> avg=90,  longest=90
    # breakeven: 300s      -> contributes to "all" only; longest_all becomes 300
    svc.create_trade(
        symbol="MGC", direction="long",
        open_time="2025-03-01T09:00:00Z", close_time="2025-03-01T09:01:00Z",
        pnl=10.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="MGC", direction="long",
        open_time="2025-03-02T09:00:00Z", close_time="2025-03-02T09:03:00Z",
        pnl=20.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="MGC", direction="short",
        open_time="2025-03-03T09:00:00Z", close_time="2025-03-03T09:01:30Z",
        pnl=-5.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="MGC", direction="long",
        open_time="2025-03-04T09:00:00Z", close_time="2025-03-04T09:05:00Z",
        pnl=0.0, user_id=USER_ID,
    )

    stats = svc.compute_stats(user_id=USER_ID)

    # Winner / loser buckets exclude breakeven:
    assert stats["avg_holding_winners"] == pytest.approx(120.0)
    assert stats["avg_holding_losers"] == pytest.approx(90.0)
    assert stats["longest_holding_winners"] == pytest.approx(180.0)
    assert stats["longest_holding_losers"] == pytest.approx(90.0)
    # Overall longest picks up the 300s breakeven trade:
    assert stats["longest_holding_all"] == pytest.approx(300.0)


def test_compute_stats_run_up_and_drawdown_timestamps(svc):
    """Equity path: +100 -> -60 -> +80 -> -40.
    Cumulative: 100, 40, 120, 80.
    Run-up: trough at start (equity 0 before first trade); peak at t3 (120). But
    first trade's +100 gains from trough 0 = 100 (new max). Then t2 loss to 40 - trough stays 0.
    Then t3 +80 -> 120, gain-from-trough = 120. That's max run-up.
    Drawdown: peak 100 at t1, trough 40 at t2 -> dd=60. Peak 120 at t3, trough 80 at t4 -> dd=40.
    Max drawdown = 60, from t1 close_time to t2 close_time.
    """
    svc.create_trade(
        symbol="MGC", direction="long",
        open_time="2025-04-01T09:00:00Z", close_time="2025-04-01T10:00:00Z",
        pnl=100.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="MGC", direction="short",
        open_time="2025-04-02T09:00:00Z", close_time="2025-04-02T10:00:00Z",
        pnl=-60.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="MGC", direction="long",
        open_time="2025-04-03T09:00:00Z", close_time="2025-04-03T10:00:00Z",
        pnl=80.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="MGC", direction="short",
        open_time="2025-04-04T09:00:00Z", close_time="2025-04-04T10:00:00Z",
        pnl=-40.0, user_id=USER_ID,
    )

    stats = svc.compute_stats(user_id=USER_ID)

    assert stats["max_drawdown"] == pytest.approx(60.0)
    assert stats["max_drawdown_from"] == "2025-04-01T10:00:00Z"
    assert stats["max_drawdown_to"] == "2025-04-02T10:00:00Z"
    assert stats["max_run_up"] == pytest.approx(120.0)
    # Trough time is the starting baseline (before any trade). We anchor to the
    # open_time of the first trade as the "from" reference.
    assert stats["max_run_up_from"] == "2025-04-01T09:00:00Z"
    assert stats["max_run_up_to"] == "2025-04-03T10:00:00Z"


def test_compute_stats_monotonic_gains_leave_drawdown_empty(svc):
    """Pure uptrend: no drawdown, so max_drawdown* timestamps stay empty."""
    svc.create_trade(
        symbol="MGC", direction="long",
        open_time="2025-07-01T09:00:00Z", close_time="2025-07-01T10:00:00Z",
        pnl=50.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="MGC", direction="long",
        open_time="2025-07-02T09:00:00Z", close_time="2025-07-02T10:00:00Z",
        pnl=30.0, user_id=USER_ID,
    )

    stats = svc.compute_stats(user_id=USER_ID)

    assert stats["max_drawdown"] == pytest.approx(0.0)
    assert stats["max_drawdown_from"] == ""
    assert stats["max_drawdown_to"] == ""
    # Run-up: full climb from baseline (t1 open) to highest equity (t2 close)
    assert stats["max_run_up"] == pytest.approx(80.0)
    assert stats["max_run_up_from"] == "2025-07-01T09:00:00Z"
    assert stats["max_run_up_to"] == "2025-07-02T10:00:00Z"


def test_compute_stats_series_fields(svc):
    """per_trade_series, distribution_series, pnl_by_hour."""
    svc.create_trade(
        symbol="MGC", direction="long",
        open_time="2025-05-01T09:00:00Z", close_time="2025-05-01T10:00:00Z",
        pnl=40.0, fees=1.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="MGC", direction="short",
        open_time="2025-05-02T14:00:00Z", close_time="2025-05-02T15:00:00Z",
        pnl=-25.0, fees=1.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="MGC", direction="long",
        open_time="2025-05-03T14:30:00Z", close_time="2025-05-03T15:30:00Z",
        pnl=10.0, fees=1.0, user_id=USER_ID,
    )

    stats = svc.compute_stats(user_id=USER_ID)

    # per_trade_series: sorted by close_time, each row has time/pnl_net/pnl_gross.
    assert len(stats["per_trade_series"]) == 3
    first = stats["per_trade_series"][0]
    assert first["time"] == "2025-05-01T10:00:00Z"
    assert first["pnl_net"] == pytest.approx(40.0)
    assert first["pnl_gross"] == pytest.approx(41.0)

    # distribution_series: ascending.
    assert stats["distribution_series"] == [pytest.approx(-25.0), pytest.approx(10.0), pytest.approx(40.0)]

    # pnl_by_hour: hour-of-day buckets from open_time.
    # 24-bucket contract: always emitted, hours with no trades have zeros
    assert len(stats["pnl_by_hour"]) == 24
    by_hour = {b["hour"]: b for b in stats["pnl_by_hour"]}
    assert all(h in by_hour for h in range(24))
    assert by_hour[9]["total_pnl"] == pytest.approx(40.0)
    assert by_hour[9]["count"] == 1
    # 14:00 trade (-25) + 14:30 trade (+10) both land in hour=14
    assert by_hour[14]["total_pnl"] == pytest.approx(-15.0)
    assert by_hour[14]["count"] == 2
    # A random empty hour:
    assert by_hour[3]["total_pnl"] == pytest.approx(0.0)
    assert by_hour[3]["count"] == 0


def test_compute_stats_run_up_falls_back_to_close_time_when_open_time_missing(svc):
    """If first trade has open_time=None, baseline trough_time falls back to close_time."""
    svc.create_trade(
        symbol="MGC", direction="long",
        open_time=None, close_time="2025-08-01T10:00:00Z",
        pnl=100.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="MGC", direction="long",
        open_time="2025-08-02T09:00:00Z", close_time="2025-08-02T10:00:00Z",
        pnl=50.0, user_id=USER_ID,
    )

    stats = svc.compute_stats(user_id=USER_ID)

    # Run-up spans from baseline (t1 close, since open is None) to t2 close.
    assert stats["max_run_up"] == pytest.approx(150.0)
    assert stats["max_run_up_from"] == "2025-08-01T10:00:00Z"
    assert stats["max_run_up_to"] == "2025-08-02T10:00:00Z"


def test_get_starting_capital_default_none(svc):
    """Brand-new user -> None."""
    assert svc.get_starting_capital(user_id=USER_ID) is None


def test_set_and_get_starting_capital(svc):
    """Round-trip a value."""
    svc.set_starting_capital(user_id=USER_ID, value=50000.0)
    assert svc.get_starting_capital(user_id=USER_ID) == pytest.approx(50000.0)


def test_set_starting_capital_upserts(svc, db):
    """Second set overwrites the first; only one row per user."""
    svc.set_starting_capital(user_id=USER_ID, value=50000.0)
    svc.set_starting_capital(user_id=USER_ID, value=30000.0)
    assert svc.get_starting_capital(user_id=USER_ID) == pytest.approx(30000.0)
    from sqlalchemy import func, select
    from models import JournalSettings
    count = db.execute(
        select(func.count()).select_from(JournalSettings).where(JournalSettings.user_id == USER_ID)
    ).scalar_one()
    assert count == 1


def test_set_starting_capital_null_clears(svc):
    """Setting None persists as NULL -> get returns None."""
    svc.set_starting_capital(user_id=USER_ID, value=50000.0)
    svc.set_starting_capital(user_id=USER_ID, value=None)
    assert svc.get_starting_capital(user_id=USER_ID) is None


def test_update_journal_currency_preserves_starting_capital(svc):
    svc.set_starting_capital(user_id=USER_ID, value=50000.0)

    settings = svc.update_journal_settings(USER_ID, {"currency_code": "USDT"})

    assert settings == {"starting_capital": 50000.0, "currency_code": "USDT"}
    assert svc.get_journal_settings(USER_ID) == settings


def test_compute_stats_pnl_before_range(svc):
    """pnl of trades closed before date_from is returned as pnl_before_range."""
    svc.create_trade(
        symbol="MGC", direction="long",
        open_time="2025-01-01T09:00:00Z", close_time="2025-01-01T10:00:00Z",
        pnl=100.0, user_id=USER_ID,
    )
    svc.create_trade(
        symbol="MGC", direction="short",
        open_time="2025-01-02T09:00:00Z", close_time="2025-01-02T10:00:00Z",
        pnl=-30.0, user_id=USER_ID,
    )
    # inside the range:
    svc.create_trade(
        symbol="MGC", direction="long",
        open_time="2025-02-01T09:00:00Z", close_time="2025-02-01T10:00:00Z",
        pnl=50.0, user_id=USER_ID,
    )

    stats = svc.compute_stats(user_id=USER_ID, date_from="2025-02-01T00:00:00Z")
    assert stats["pnl_before_range"] == pytest.approx(70.0)  # 100 + (-30)


def test_compute_stats_pnl_before_range_zero_when_no_date_from(svc):
    """No filter -> 0.0."""
    svc.create_trade(
        symbol="MGC", direction="long",
        open_time="2025-01-01T09:00:00Z", close_time="2025-01-01T10:00:00Z",
        pnl=100.0, user_id=USER_ID,
    )
    stats = svc.compute_stats(user_id=USER_ID)
    assert stats["pnl_before_range"] == pytest.approx(0.0)


def test_compute_stats_pnl_before_range_no_in_range_trades(svc):
    """Trades exist before range but none in range -> correct pnl_before_range."""
    svc.create_trade(
        symbol="MGC", direction="long",
        open_time="2025-01-01T09:00:00Z", close_time="2025-01-01T10:00:00Z",
        pnl=100.0, user_id=USER_ID,
    )
    stats = svc.compute_stats(user_id=USER_ID, date_from="2025-02-01T00:00:00Z")
    assert stats["total_trades"] == 0
    assert stats["pnl_before_range"] == pytest.approx(100.0)


def _seed_strategy(db, user_id: str, title: str = "S") -> str:
    sid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    db.add(Strategy(id=sid, user_id=user_id, title=title, body="", tags="[]", created_at=now, updated_at=now))
    db.flush()
    return sid


def test_create_trade_persists_strategy_id(svc, db):
    sid = _seed_strategy(db, USER_ID)
    t = svc.create_trade(symbol="XAUUSD", direction="long", user_id=USER_ID, strategy_id=sid)
    assert t["strategy_id"] == sid


def test_create_trade_rejects_other_users_strategy(svc, db):
    sid = _seed_strategy(db, "alice")
    with pytest.raises(PermissionError):
        svc.create_trade(symbol="XAUUSD", direction="long", user_id=USER_ID, strategy_id=sid)


def test_update_trade_can_clear_strategy(svc, db):
    sid = _seed_strategy(db, USER_ID)
    t = svc.create_trade(symbol="XAUUSD", direction="long", user_id=USER_ID, strategy_id=sid)
    updated = svc.update_trade(trade_id=t["id"], user_id=USER_ID, strategy_id=None)
    assert updated["strategy_id"] is None

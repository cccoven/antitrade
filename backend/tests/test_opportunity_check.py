from services.journal import JournalService
from services.opportunity_check import check_trade_opportunity


def _snapshot(asset_class="stock", symbol="AAPL", price=102.0):
    return {
        "provider": "test",
        "asset_class": asset_class,
        "symbol": symbol,
        "interval": "1day",
        "as_of": "2026-07-17T00:00:00+00:00",
        "quote": {"price": price, "percent_change": 1.0},
        "technicals": {},
        "recent_candles": [],
        "warnings": [],
    }


def test_opportunity_check_combines_rules_plan_and_history(db, user_id):
    journal = JournalService(db)
    journal.create_rule(user_id, "Max 1%", "max_risk_percent", 1, "critical")
    journal.create_rule(user_id, "Minimum 2R", "min_risk_reward", 2, "important")
    plan = journal.create_trade_plan(
        user_id=user_id,
        symbol="AAPL",
        market="stock",
        direction="long",
        entry_price=100,
        stop_loss=95,
        target_price=110,
        account_size=1000,
        risk_percent=1,
        thesis="Retest",
        strategy_id=None,
    )
    for index in range(10):
        journal.create_trade(
            user_id=user_id,
            symbol="AAPL",
            direction="long",
            pnl=100 if index % 2 == 0 else -50,
            open_time=f"2026-06-{index + 1:02d}T10:00:00Z",
            close_time=f"2026-06-{index + 1:02d}T11:00:00Z",
        )

    result = check_trade_opportunity(
        db,
        user_id,
        market="stock",
        symbol="AAPL",
        direction="long",
        entry_price=100,
        stop_loss=95,
        target_price=110,
        quantity=2,
        account_size=1000,
        snapshot=_snapshot(),
    )

    assert result["verdict"] == "compliant"
    assert result["plan_match"]["plan"]["id"] == plan["id"]
    assert result["risk"]["risk_amount"] == 10
    assert result["risk"]["risk_percent"] == 1
    assert result["risk"]["reward_risk"] == 2
    assert result["risk"]["max_quantity"] == 2
    assert result["compliance"]["failed"] == 0
    assert result["history"]["sample_count"] == 10
    assert result["history"]["sample_quality"] == "limited"
    assert result["history"]["win_rate"] == 50


def test_futures_opportunity_uses_contract_point_value(db, user_id):
    journal = JournalService(db)
    journal.create_rule(user_id, "Max 1%", "max_risk_percent", 1, "critical")

    result = check_trade_opportunity(
        db,
        user_id,
        market="futures",
        symbol="MNQ",
        direction="long",
        entry_price=20000,
        stop_loss=19990,
        target_price=20020,
        quantity=2,
        account_size=10000,
        snapshot=_snapshot("futures", "MNQ", 20005),
    )

    assert result["risk"]["risk_amount"] == 40
    assert result["risk"]["risk_percent"] == 0.4
    assert result["compliance"]["failed"] == 0
    assert result["verdict"] == "compliant"


def test_unknown_instrument_marks_critical_risk_rule_not_applicable(db, user_id):
    journal = JournalService(db)
    journal.create_rule(user_id, "Max 1%", "max_risk_percent", 1, "critical")

    result = check_trade_opportunity(
        db,
        user_id,
        market="forex",
        symbol="EURUSD",
        direction="long",
        entry_price=1.1,
        stop_loss=1.09,
        quantity=10000,
        account_size=10000,
        snapshot=_snapshot("forex", "EUR/USD", 1.101),
    )

    assert result["risk"]["risk_amount"] is None
    assert result["compliance"]["not_applicable"] == 1
    assert result["verdict"] == "insufficient_data"
    assert "instrument_spec_unavailable" in result["warnings"]


def test_plan_id_is_user_scoped(db, user_id):
    result = check_trade_opportunity(db, user_id, plan_id="not-owned")
    assert result == {"error": "plan_not_found"}

import pytest

from services.risk_engine import (
    PositionRiskInput,
    calculate_position_risk,
)
from services.trading_tools import (
    calculate_cost_impact,
    calculate_drawdown,
    calculate_expectancy,
    calculate_monte_carlo,
)


def test_position_size_uses_contract_value_and_rounds_futures():
    result = calculate_position_risk(PositionRiskInput(
        asset_class="futures",
        symbol="MNQ",
        direction="long",
        entry_price=20_000,
        stop_loss=19_990,
        target_price=20_020,
        account_size=10_000,
        risk_percent=1,
    ))

    assert result.point_value == 2
    assert result.unit_risk == 20
    assert result.risk_budget == 100
    assert result.quantity == 5
    assert result.risk_amount == 100
    assert result.reward_risk == 2
    assert result.potential_reward == 200


def test_position_size_requires_explicit_value_for_unknown_instrument():
    unknown = calculate_position_risk(PositionRiskInput(
        asset_class="forex",
        symbol="EURUSD",
        direction="long",
        entry_price=1.1,
        stop_loss=1.09,
        account_size=10_000,
        risk_percent=1,
    ))
    explicit = calculate_position_risk(PositionRiskInput(
        asset_class="forex",
        symbol="EURUSD",
        direction="long",
        entry_price=1.1,
        stop_loss=1.09,
        account_size=10_000,
        risk_percent=1,
        point_value=100_000,
    ))

    assert unknown.quantity is None
    assert "point_value_required" in unknown.warnings
    assert explicit.quantity == pytest.approx(0.1)
    assert explicit.risk_amount == pytest.approx(100)


def test_expectancy_includes_cost_and_target_trade_count():
    result = calculate_expectancy(
        win_rate=50,
        avg_win=150,
        avg_loss=100,
        cost_per_trade=5,
        target_profit=1_000,
    )

    assert result["gross_expectancy"] == 25
    assert result["expectancy"] == 20
    assert result["break_even_win_rate"] == 42
    assert result["trades_to_target"] == 50


def test_drawdown_reports_recovery_and_loss_capacity():
    result = calculate_drawdown(
        starting_equity=10_000,
        current_equity=9_000,
        max_drawdown_percent=20,
        risk_per_trade_percent=1,
    )

    assert result["drawdown_percent"] == 10
    assert result["recovery_gain_percent"] == pytest.approx(11.111111)
    assert result["floor_equity"] == 8_000
    assert result["remaining_loss_budget"] == 1_000
    assert result["losses_until_limit"] == 11
    assert result["limit_breached"] is False


def test_monte_carlo_is_reproducible_and_returns_percentile_path():
    params = dict(
        starting_equity=10_000,
        target_return_percent=10,
        max_drawdown_percent=20,
        win_rate=55,
        avg_win_r=1.5,
        avg_loss_r=1,
        risk_per_trade_percent=1,
        trades=50,
        simulations=200,
        seed=7,
    )

    first = calculate_monte_carlo(**params)
    second = calculate_monte_carlo(**params)

    assert first == second
    assert len(first["percentile_bands"]) == 51
    assert 0 <= first["target_probability"] <= 100
    assert 0 <= first["risk_of_ruin"] <= 100


def test_cost_impact_reconciles_gross_and_net_pnl():
    result = calculate_cost_impact(
        trades_count=100,
        gross_pnl=2_000,
        commission_per_trade=2,
        slippage_per_trade=1,
        spread_per_trade=0.5,
    )

    assert result["cost_per_trade"] == 3.5
    assert result["total_cost"] == 350
    assert result["net_pnl"] == 1_650
    assert result["net_average"] == 16.5
    assert result["cost_drag_percent"] == 17.5

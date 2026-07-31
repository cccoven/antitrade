import pandas as pd
import pytest

from services.backtesting_py_adapter import BacktestingPyAdapter


def _candles(
    opens: list[float],
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
) -> pd.DataFrame:
    highs = highs or [max(open_, close) + 0.5 for open_, close in zip(opens, closes)]
    lows = lows or [min(open_, close) - 0.5 for open_, close in zip(opens, closes)]
    return pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [100.0] * len(opens),
        },
        index=pd.date_range("2025-01-01", periods=len(opens), freq="D"),
    )


def _condition(left: dict, operator: str, right: dict) -> dict:
    return {"left": left, "operator": operator, "right": right}


def test_signal_executes_at_next_bar_open_and_maps_trade():
    data = _candles(
        opens=[10, 11, 12, 13, 14, 15, 16, 17],
        closes=[10, 11, 12, 13, 14, 15, 16, 17],
    )
    config = {
        "direction": "long",
        "entry_conditions": [
            _condition(
                {"type": "price", "field": "close"},
                "cross_above",
                {"type": "value", "value": 10.5},
            )
        ],
        "exit_conditions": [
            _condition(
                {"type": "price", "field": "close"},
                ">",
                {"type": "value", "value": 13},
            )
        ],
    }

    result = BacktestingPyAdapter().run(config, data)

    assert result["engine"]["name"] == "backtesting.py"
    assert result["engine"]["execution"] == "signal_close_next_open"
    assert result["total_trades"] == 1
    assert result["total_pnl"] == pytest.approx(3.0)
    assert result["equity_curve"][0]["equity"] == pytest.approx(100_000)
    assert result["equity_curve"][-1]["equity"] == pytest.approx(100_003)
    assert result["trades"][0] == {
        "direction": "long",
        "entry_time": "2025-01-03T00:00:00",
        "exit_time": "2025-01-06T00:00:00",
        "entry_price": 12.0,
        "exit_price": 15.0,
        "size": 1.0,
        "pnl": 3.0,
        "commission": 0.0,
        "return_pct": 0.25,
        "exit_reason": "condition_or_end",
    }


def test_commission_is_included_in_trade_and_total_pnl():
    data = _candles(
        opens=[10, 11, 12, 13, 14, 15, 16, 17],
        closes=[10, 11, 12, 13, 14, 15, 16, 17],
    )
    config = {
        "direction": "long",
        "commission_bps": 100,
        "entry_conditions": [
            _condition(
                {"type": "price", "field": "close"},
                "cross_above",
                {"type": "value", "value": 10.5},
            )
        ],
        "exit_conditions": [
            _condition(
                {"type": "price", "field": "close"},
                ">",
                {"type": "value", "value": 13},
            )
        ],
    }

    result = BacktestingPyAdapter().run(config, data)

    assert result["trades"][0]["commission"] == pytest.approx(0.27)
    assert result["trades"][0]["pnl"] == pytest.approx(2.73)
    assert result["total_pnl"] == pytest.approx(2.73)


def test_short_take_profit_is_handled_by_engine():
    data = _candles(
        opens=[10, 11, 10, 10, 9, 8],
        closes=[10, 11, 10, 9, 8, 8],
        highs=[10.5, 11.5, 10.5, 10.5, 9.5, 8.5],
        lows=[9.5, 10.5, 9.5, 8.5, 7.5, 7.5],
    )
    config = {
        "direction": "short",
        "take_profit_pct": 10,
        "entry_conditions": [
            _condition(
                {"type": "price", "field": "close"},
                "cross_below",
                {"type": "value", "value": 10.5},
            )
        ],
        "exit_conditions": [],
    }

    result = BacktestingPyAdapter().run(config, data)

    assert result["total_trades"] == 1
    assert result["trades"][0]["direction"] == "short"
    assert result["trades"][0]["exit_reason"] == "take_profit"
    assert result["trades"][0]["pnl"] > 0


def test_invalid_direction_is_rejected():
    data = _candles(opens=[10, 11, 12], closes=[10, 11, 12])

    with pytest.raises(ValueError, match="long or short"):
        BacktestingPyAdapter().run(
            {
                "direction": "both",
                "entry_conditions": [],
                "exit_conditions": [],
            },
            data,
        )


def test_condition_groups_support_or_logic():
    data = _candles(
        opens=[10, 11, 12, 13, 14, 9, 8],
        closes=[10, 11, 12, 13, 14, 9, 8],
    )
    config = {
        "direction": "long",
        "entry_groups_operator": "or",
        "entry_groups": [
            {
                "operator": "or",
                "conditions": [
                    _condition(
                        {"type": "price", "field": "close"},
                        "cross_above",
                        {"type": "value", "value": 10.5},
                    ),
                    _condition(
                        {"type": "price", "field": "close"},
                        ">",
                        {"type": "value", "value": 100},
                    ),
                ],
            }
        ],
        "exit_groups": [
            {
                "operator": "and",
                "conditions": [
                    _condition(
                        {"type": "price", "field": "close"},
                        "<",
                        {"type": "value", "value": 10},
                    )
                ],
            }
        ],
    }

    result = BacktestingPyAdapter().run(config, data)

    assert result["total_trades"] == 1


def test_time_exit_closes_position_after_configured_bars():
    data = _candles(
        opens=[10, 11, 12, 13, 14, 15, 16],
        closes=[10, 11, 12, 13, 14, 15, 16],
    )
    config = {
        "direction": "long",
        "max_holding_bars": 2,
        "entry_conditions": [
            _condition(
                {"type": "price", "field": "close"},
                "cross_above",
                {"type": "value", "value": 10.5},
            )
        ],
        "exit_conditions": [],
    }

    result = BacktestingPyAdapter().run(config, data)

    assert result["trades"][0]["exit_reason"] == "time_exit"


def test_trailing_stop_and_breakeven_are_engine_managed():
    trailing_data = _candles(
        opens=[10, 11, 12, 15, 14, 13],
        closes=[10, 11, 12, 15, 14, 13],
        highs=[10.5, 11.5, 12.5, 15.5, 14.5, 13.5],
        lows=[9.5, 10.5, 11.5, 14.5, 13.0, 12.5],
    )
    base_config = {
        "direction": "long",
        "entry_conditions": [
            _condition(
                {"type": "price", "field": "close"},
                "cross_above",
                {"type": "value", "value": 10.5},
            )
        ],
        "exit_conditions": [],
    }

    trailing = BacktestingPyAdapter().run(
        {**base_config, "trailing_stop_pct": 10},
        trailing_data,
    )
    assert trailing["trades"][0]["exit_reason"] == "trailing_stop"

    breakeven_data = _candles(
        opens=[10, 11, 12, 14, 12, 12],
        closes=[10, 11, 12, 14, 12, 12],
        highs=[10.5, 11.5, 12.5, 14.5, 12.5, 12.5],
        lows=[9.5, 10.5, 11.5, 13.5, 11.0, 11.5],
    )
    breakeven = BacktestingPyAdapter().run(
        {**base_config, "breakeven_trigger_pct": 10},
        breakeven_data,
    )
    assert breakeven["trades"][0]["exit_reason"] == "breakeven"

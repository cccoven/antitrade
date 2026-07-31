import pandas as pd

from services.backtest_analysis import BacktestAnalysis


def _candles(count: int = 60) -> pd.DataFrame:
    closes = [100 + index * 0.5 + (index % 7 - 3) * 0.2 for index in range(count)]
    return pd.DataFrame(
        {
            "open": closes,
            "high": [value + 1 for value in closes],
            "low": [value - 1 for value in closes],
            "close": closes,
            "volume": [1000.0] * count,
        },
        index=pd.date_range("2025-01-01", periods=count, freq="D"),
    )


def _config() -> dict:
    return {
        "direction": "long",
        "initial_cash": 100_000,
        "position_size": 1,
        "entry_conditions": [
            {
                "left": {"type": "price", "field": "close"},
                "operator": ">",
                "right": {"type": "value", "value": 0},
            }
        ],
        "exit_conditions": [],
    }


def test_parameter_optimization_returns_ranked_trials_and_best_result():
    result = BacktestAnalysis().optimize(
        _config(),
        _candles(),
        {
            "objective": "total_return_pct",
            "grids": [
                {"parameter": "max_holding_bars", "values": [3, 5, 10]},
                {"parameter": "position_size", "values": [1, 2]},
            ],
        },
    )

    assert result["kind"] == "optimization"
    assert result["trial_count"] == 6
    assert result["best_parameters"]
    assert result["best_result"]["engine"]["name"] == "backtesting.py"
    assert len(result["trials"]) == 6


def test_out_of_sample_validation_reports_both_sides():
    result = BacktestAnalysis().validate_out_of_sample(
        _config(),
        _candles(),
        {"train_ratio": 0.7},
    )

    assert result["kind"] == "validation"
    assert result["split_time"]
    assert result["train_result"]["total_trades"] > 0
    assert result["test_result"]["total_trades"] > 0
    assert set(result["degradation"]) == {
        "total_return_pct",
        "sharpe_ratio",
        "win_rate",
    }


def test_walk_forward_optimizes_each_training_window_and_tests_next_window():
    result = BacktestAnalysis().walk_forward(
        _config(),
        _candles(),
        {
            "objective": "total_return_pct",
            "grids": [
                {"parameter": "max_holding_bars", "values": [3, 5]},
            ],
            "train_bars": 20,
            "test_bars": 10,
            "step_bars": 10,
        },
    )

    assert result["kind"] == "walk_forward"
    assert result["window_count"] == 4
    assert len(result["windows"]) == 4
    assert result["summary"]["total_trades"] > 0

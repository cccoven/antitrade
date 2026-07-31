"""Parameter search and out-of-sample validation built on one engine adapter."""

from __future__ import annotations

import copy
import itertools
import math
from typing import Any

import pandas as pd

from services.backtesting_py_adapter import BacktestingPyAdapter

MAX_OPTIMIZATION_TRIALS = 200
ALLOWED_PARAMETERS = {
    "stop_loss_pct",
    "take_profit_pct",
    "trailing_stop_pct",
    "breakeven_trigger_pct",
    "max_holding_bars",
    "position_size",
}
ALLOWED_OBJECTIVES = {
    "total_return_pct",
    "sharpe_ratio",
    "profit_factor",
    "max_drawdown_pct",
}


class BacktestAnalysis:
    def __init__(self, adapter: BacktestingPyAdapter | None = None):
        self.adapter = adapter or BacktestingPyAdapter()

    def optimize(
        self,
        config: dict[str, Any],
        candles: pd.DataFrame,
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        objective = self._objective(analysis.get("objective"))
        trials = self._evaluate_grid(
            config,
            candles,
            analysis.get("grids") or [],
            objective,
        )
        best = trials[0]
        best_config = self._with_parameters(config, best["parameters"])
        return {
            "kind": "optimization",
            "objective": objective,
            "trial_count": len(trials),
            "best_parameters": best["parameters"],
            "best_result": self.adapter.run(best_config, candles),
            "trials": trials,
        }

    def validate_out_of_sample(
        self,
        config: dict[str, Any],
        candles: pd.DataFrame,
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        ratio = float(analysis.get("train_ratio", 0.7))
        if not 0.5 <= ratio <= 0.9:
            raise ValueError("Training ratio must be between 0.5 and 0.9")
        split = int(len(candles) * ratio)
        if split < 3 or len(candles) - split < 3:
            raise ValueError("The selected period is too short for validation")
        train = candles.iloc[:split]
        test = candles.iloc[split:]
        train_result = self.adapter.run(config, train)
        test_result = self.adapter.run(config, test)
        return {
            "kind": "validation",
            "train_ratio": ratio,
            "split_time": self._iso_time(candles.index[split]),
            "train_result": train_result,
            "test_result": test_result,
            "degradation": {
                "total_return_pct": (
                    test_result["total_return_pct"]
                    - train_result["total_return_pct"]
                ),
                "sharpe_ratio": (
                    test_result["sharpe_ratio"] - train_result["sharpe_ratio"]
                ),
                "win_rate": test_result["win_rate"] - train_result["win_rate"],
            },
        }

    def walk_forward(
        self,
        config: dict[str, Any],
        candles: pd.DataFrame,
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        train_bars = int(analysis.get("train_bars", 500))
        test_bars = int(analysis.get("test_bars", 100))
        step_bars = int(analysis.get("step_bars", test_bars))
        if min(train_bars, test_bars, step_bars) < 3:
            raise ValueError("Walk-forward windows must contain at least three bars")
        objective = self._objective(analysis.get("objective"))
        grids = analysis.get("grids") or []

        windows: list[dict[str, Any]] = []
        start = 0
        while start + train_bars + test_bars <= len(candles):
            train = candles.iloc[start : start + train_bars]
            test = candles.iloc[
                start + train_bars : start + train_bars + test_bars
            ]
            trials = self._evaluate_grid(config, train, grids, objective)
            best = trials[0]
            test_config = self._with_parameters(config, best["parameters"])
            test_result = self.adapter.run(test_config, test)
            windows.append(
                {
                    "train_start": self._iso_time(train.index[0]),
                    "train_end": self._iso_time(train.index[-1]),
                    "test_start": self._iso_time(test.index[0]),
                    "test_end": self._iso_time(test.index[-1]),
                    "best_parameters": best["parameters"],
                    "train_metrics": best["metrics"],
                    "test_metrics": self._compact_metrics(test_result),
                }
            )
            start += step_bars

        if not windows:
            raise ValueError("The selected period is too short for walk-forward testing")
        returns = [
            window["test_metrics"]["total_return_pct"]
            for window in windows
        ]
        return {
            "kind": "walk_forward",
            "objective": objective,
            "train_bars": train_bars,
            "test_bars": test_bars,
            "step_bars": step_bars,
            "window_count": len(windows),
            "summary": {
                "average_test_return_pct": sum(returns) / len(returns),
                "compounded_test_return_pct": math.prod(
                    1 + value for value in returns
                )
                - 1,
                "profitable_windows": sum(value > 0 for value in returns),
                "total_trades": sum(
                    window["test_metrics"]["total_trades"]
                    for window in windows
                ),
            },
            "windows": windows,
        }

    def _evaluate_grid(
        self,
        config: dict[str, Any],
        candles: pd.DataFrame,
        grids: list[dict[str, Any]],
        objective: str,
    ) -> list[dict[str, Any]]:
        normalized = self._normalize_grids(grids)
        combinations = list(
            itertools.product(*(grid["values"] for grid in normalized))
        )
        if len(combinations) > MAX_OPTIMIZATION_TRIALS:
            raise ValueError(
                f"Parameter search is limited to {MAX_OPTIMIZATION_TRIALS} trials"
            )

        trials = []
        for values in combinations:
            parameters = {
                grid["parameter"]: value
                for grid, value in zip(normalized, values)
            }
            trial_config = self._with_parameters(config, parameters)
            result = self.adapter.run(trial_config, candles)
            metrics = self._compact_metrics(result)
            trials.append(
                {
                    "parameters": parameters,
                    "metrics": metrics,
                    "_score": self._score(metrics, objective),
                }
            )
        trials.sort(key=lambda item: item["_score"], reverse=True)
        for trial in trials:
            trial.pop("_score", None)
        return trials

    @staticmethod
    def _normalize_grids(grids: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not grids:
            raise ValueError("At least one parameter grid is required")
        normalized = []
        seen = set()
        for grid in grids:
            parameter = str(grid.get("parameter", ""))
            if parameter not in ALLOWED_PARAMETERS:
                raise ValueError(f"Unsupported optimization parameter: {parameter}")
            if parameter in seen:
                raise ValueError(f"Duplicate optimization parameter: {parameter}")
            values = list(grid.get("values") or [])
            if not values:
                raise ValueError(f"Parameter grid has no values: {parameter}")
            if any(
                not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in values
            ):
                raise ValueError(f"Parameter values must be finite: {parameter}")
            seen.add(parameter)
            normalized.append({"parameter": parameter, "values": values})
        return normalized

    @staticmethod
    def _with_parameters(
        config: dict[str, Any],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        updated = copy.deepcopy(config)
        updated.update(parameters)
        return updated

    @staticmethod
    def _objective(value: Any) -> str:
        objective = str(value or "sharpe_ratio")
        if objective not in ALLOWED_OBJECTIVES:
            raise ValueError(f"Unsupported optimization objective: {objective}")
        return objective

    @staticmethod
    def _score(metrics: dict[str, Any], objective: str) -> float:
        value = metrics.get(objective)
        if value is None or not math.isfinite(float(value)):
            return -math.inf
        numeric = float(value)
        return -numeric if objective == "max_drawdown_pct" else numeric

    @staticmethod
    def _compact_metrics(result: dict[str, Any]) -> dict[str, Any]:
        return {
            "total_return_pct": result["total_return_pct"],
            "total_pnl": result["total_pnl"],
            "total_trades": result["total_trades"],
            "win_rate": result["win_rate"],
            "profit_factor": result["profit_factor"],
            "max_drawdown_pct": result["max_drawdown_pct"],
            "sharpe_ratio": result["sharpe_ratio"],
        }

    @staticmethod
    def _iso_time(value: Any) -> str:
        return value.isoformat() if hasattr(value, "isoformat") else str(value)

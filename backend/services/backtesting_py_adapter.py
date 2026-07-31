"""Adapter from AntiTrade's condition config to backtesting.py.

This module intentionally contains no database or market-data concerns.  It
accepts a strategy config plus an OHLCV DataFrame and returns the stable result
shape consumed by the frontend.
"""

from __future__ import annotations

import math
from typing import Any

import backtesting
import numpy as np
import pandas as pd
import talib
from backtesting import Backtest, Strategy

MAX_EQUITY_POINTS = 1500


class BacktestingPyAdapter:
    """Run one single-symbol, single-timeframe condition strategy."""

    def run(self, config: dict[str, Any], candles: pd.DataFrame) -> dict[str, Any]:
        data = self._prepare_data(config, candles)
        strategy_type = self._build_strategy(config)

        initial_cash = self._positive_number(config.get("initial_cash"), 100_000.0)
        commission_bps = self._non_negative_number(config.get("commission_bps"), 0.0)
        spread_bps = self._non_negative_number(config.get("spread_bps"), 0.0)
        position_size = self._position_size(config.get("position_size"))

        stats = Backtest(
            data,
            strategy_type,
            cash=initial_cash,
            commission=commission_bps / 10_000,
            spread=spread_bps / 10_000,
            trade_on_close=False,
            hedging=False,
            exclusive_orders=True,
            finalize_trades=True,
        ).run()

        return self._map_result(
            stats,
            config=config,
            data=data,
            initial_cash=initial_cash,
            position_size=position_size,
            commission_bps=commission_bps,
            spread_bps=spread_bps,
        )

    def _prepare_data(self, config: dict[str, Any], candles: pd.DataFrame) -> pd.DataFrame:
        if candles is None or candles.empty:
            raise ValueError("No market data available for this backtest")

        source = candles.copy()
        source.columns = [str(column).lower() for column in source.columns]
        required = ("open", "high", "low", "close")
        missing = [column for column in required if column not in source.columns]
        if missing:
            raise ValueError(f"Market data is missing columns: {', '.join(missing)}")

        if not isinstance(source.index, pd.DatetimeIndex):
            source.index = pd.to_datetime(source.index, errors="coerce")
        source = source.loc[~source.index.isna()]
        source = source[~source.index.duplicated(keep="last")].sort_index()

        for column in (*required, "volume"):
            if column in source.columns:
                source[column] = pd.to_numeric(source[column], errors="coerce")
        if "volume" not in source.columns:
            source["volume"] = 0.0
        source = source.dropna(subset=list(required))
        if len(source) < 3:
            raise ValueError("At least three valid OHLC bars are required")

        entry_signal = self._combine_groups(
            source,
            config.get("entry_groups"),
            config.get("entry_groups_operator", "or"),
            legacy_conditions=config.get("entry_conditions"),
        )
        exit_signal = self._combine_groups(
            source,
            config.get("exit_groups"),
            config.get("exit_groups_operator", "or"),
            legacy_conditions=config.get("exit_conditions"),
        )

        return pd.DataFrame(
            {
                "Open": source["open"].astype(float),
                "High": source["high"].astype(float),
                "Low": source["low"].astype(float),
                "Close": source["close"].astype(float),
                "Volume": source["volume"].fillna(0).astype(float),
                "EntrySignal": entry_signal.astype(bool),
                "ExitSignal": exit_signal.astype(bool),
            },
            index=source.index,
        )

    def _combine_conditions(
        self,
        data: pd.DataFrame,
        conditions: list[dict[str, Any]],
        operator: str = "and",
    ) -> pd.Series:
        if not conditions:
            return pd.Series(False, index=data.index, dtype=bool)

        signals = [self._condition_series(data, condition) for condition in conditions]
        frame = pd.concat(signals, axis=1).fillna(False)
        return frame.any(axis=1) if operator == "or" else frame.all(axis=1)

    def _combine_groups(
        self,
        data: pd.DataFrame,
        groups: list[dict[str, Any]] | None,
        groups_operator: str,
        *,
        legacy_conditions: list[dict[str, Any]] | None,
    ) -> pd.Series:
        normalized_groups = groups
        if normalized_groups is None:
            normalized_groups = (
                [{"operator": "and", "conditions": legacy_conditions}]
                if legacy_conditions
                else []
            )
        if not normalized_groups:
            return pd.Series(False, index=data.index, dtype=bool)
        signals = [
            self._combine_conditions(
                data,
                group.get("conditions") or [],
                str(group.get("operator", "and")),
            )
            for group in normalized_groups
        ]
        frame = pd.concat(signals, axis=1).fillna(False)
        return frame.all(axis=1) if groups_operator == "and" else frame.any(axis=1)

    def _condition_series(
        self, data: pd.DataFrame, condition: dict[str, Any]
    ) -> pd.Series:
        left = self._reference_series(data, condition.get("left") or {})
        right = self._reference_series(data, condition.get("right") or {})
        operator = condition.get("operator")

        if operator in (">", "gt"):
            result = left > right
        elif operator in ("<", "lt"):
            result = left < right
        elif operator == ">=":
            result = left >= right
        elif operator == "<=":
            result = left <= right
        elif operator == "==":
            result = left == right
        elif operator == "cross_above":
            result = (left.shift(1) <= right.shift(1)) & (left > right)
        elif operator == "cross_below":
            result = (left.shift(1) >= right.shift(1)) & (left < right)
        else:
            raise ValueError(f"Unsupported condition operator: {operator}")

        return result.fillna(False)

    def _reference_series(
        self, data: pd.DataFrame, reference: dict[str, Any]
    ) -> pd.Series:
        ref_type = reference.get("type")
        params = reference.get("params") or {}
        close = data["close"].to_numpy(dtype=float)

        if ref_type == "value":
            try:
                value = float(reference["value"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("A numeric comparison value is required") from exc
            return pd.Series(value, index=data.index, dtype=float)

        if ref_type == "price":
            field = str(reference.get("field", "close")).lower()
            if field not in ("open", "high", "low", "close"):
                raise ValueError(f"Unsupported price field: {field}")
            return data[field].astype(float)

        if ref_type in ("ema", "sma", "rsi", "atr"):
            period = self._positive_integer(params.get("period"), 14)
            if ref_type == "ema":
                values = talib.EMA(close, timeperiod=period)
            elif ref_type == "sma":
                values = talib.SMA(close, timeperiod=period)
            elif ref_type == "rsi":
                values = talib.RSI(close, timeperiod=period)
            else:
                values = talib.ATR(
                    data["high"].to_numpy(dtype=float),
                    data["low"].to_numpy(dtype=float),
                    close,
                    timeperiod=period,
                )
            return pd.Series(values, index=data.index)

        if ref_type == "macd":
            fast = self._positive_integer(params.get("fast"), 12)
            slow = self._positive_integer(params.get("slow"), 26)
            signal_period = self._positive_integer(params.get("signal"), 9)
            main, signal, histogram = talib.MACD(
                close,
                fastperiod=fast,
                slowperiod=slow,
                signalperiod=signal_period,
            )
            field = reference.get("field") or params.get("field") or "main"
            values = {"main": main, "signal": signal, "hist": histogram}.get(str(field))
            if values is None:
                raise ValueError(f"Unsupported MACD field: {field}")
            return pd.Series(values, index=data.index)

        if ref_type == "bollinger":
            period = self._positive_integer(params.get("period"), 20)
            upper, middle, lower = talib.BBANDS(close, timeperiod=period)
            field = reference.get("field") or params.get("field") or "middle"
            values = {"upper": upper, "middle": middle, "lower": lower}.get(str(field))
            if values is None:
                raise ValueError(f"Unsupported Bollinger field: {field}")
            return pd.Series(values, index=data.index)

        raise ValueError(f"Unsupported condition reference: {ref_type}")

    @staticmethod
    def _build_strategy(config: dict[str, Any]) -> type[Strategy]:
        direction = config.get("direction", "long")
        if direction not in ("long", "short"):
            raise ValueError("Direction must be either long or short")

        stop_loss_pct = BacktestingPyAdapter._optional_positive_number(
            config.get("stop_loss_pct", config.get("stop_loss"))
        )
        take_profit_pct = BacktestingPyAdapter._optional_positive_number(
            config.get("take_profit_pct", config.get("take_profit"))
        )
        trailing_stop_pct = BacktestingPyAdapter._optional_positive_number(
            config.get("trailing_stop_pct")
        )
        breakeven_trigger_pct = BacktestingPyAdapter._optional_positive_number(
            config.get("breakeven_trigger_pct")
        )
        max_holding_bars = BacktestingPyAdapter._optional_positive_integer(
            config.get("max_holding_bars")
        )
        position_size = BacktestingPyAdapter._position_size(config.get("position_size"))

        class ConditionStrategy(Strategy):
            def init(self) -> None:
                return None

            def next(self) -> None:
                if not self.position:
                    if not bool(self.data.EntrySignal[-1]):
                        return

                    price = float(self.data.Close[-1])
                    if direction == "long":
                        stop = price * (1 - stop_loss_pct / 100) if stop_loss_pct else None
                        target = (
                            price * (1 + take_profit_pct / 100)
                            if take_profit_pct
                            else None
                        )
                        self.buy(size=position_size, sl=stop, tp=target)
                    else:
                        stop = price * (1 + stop_loss_pct / 100) if stop_loss_pct else None
                        target = (
                            price * (1 - take_profit_pct / 100)
                            if take_profit_pct
                            else None
                        )
                        self.sell(size=position_size, sl=stop, tp=target)
                    return

                trade = self.trades[-1]
                current_price = float(self.data.Close[-1])
                if trailing_stop_pct:
                    if trade.is_long:
                        candidate = current_price * (1 - trailing_stop_pct / 100)
                        trade.sl = max(trade.sl or -math.inf, candidate)
                    else:
                        candidate = current_price * (1 + trailing_stop_pct / 100)
                        trade.sl = min(trade.sl or math.inf, candidate)

                if breakeven_trigger_pct:
                    trigger = breakeven_trigger_pct / 100
                    reached = (
                        trade.is_long
                        and current_price >= trade.entry_price * (1 + trigger)
                    ) or (
                        trade.is_short
                        and current_price <= trade.entry_price * (1 - trigger)
                    )
                    if reached:
                        if trade.is_long:
                            trade.sl = max(trade.sl or -math.inf, trade.entry_price)
                        else:
                            trade.sl = min(trade.sl or math.inf, trade.entry_price)

                if (
                    max_holding_bars
                    and len(self.data) - 1 - trade.entry_bar >= max_holding_bars
                ):
                    self.position.close()
                    return

                if bool(self.data.ExitSignal[-1]):
                    self.position.close()

        ConditionStrategy.__name__ = "AntiTradeConditionStrategy"
        return ConditionStrategy

    @staticmethod
    def _map_result(
        stats: pd.Series,
        *,
        config: dict[str, Any],
        data: pd.DataFrame,
        initial_cash: float,
        position_size: float,
        commission_bps: float,
        spread_bps: float,
    ) -> dict[str, Any]:
        trades_frame = stats["_trades"]
        equity_frame = stats["_equity_curve"]

        trades = [
            BacktestingPyAdapter._map_trade(row, config)
            for _, row in trades_frame.iterrows()
        ]
        pnls = [trade["pnl"] for trade in trades]
        wins = [pnl for pnl in pnls if pnl > 0]
        losses = [pnl for pnl in pnls if pnl <= 0]

        total_pnl = BacktestingPyAdapter._finite_float(
            stats.get("Equity Final [$]"), initial_cash
        ) - initial_cash
        max_drawdown = BacktestingPyAdapter._max_currency_drawdown(equity_frame)
        profit_factor = BacktestingPyAdapter._optional_finite_float(
            stats.get("Profit Factor")
        )

        return {
            "engine": {
                "name": "backtesting.py",
                "version": backtesting.__version__,
                "execution": "signal_close_next_open",
            },
            "assumptions": {
                "initial_cash": initial_cash,
                "position_size": position_size,
                "commission_bps": commission_bps,
                "spread_bps": spread_bps,
            },
            "total_pnl": total_pnl,
            "total_return_pct": BacktestingPyAdapter._finite_float(
                stats.get("Return [%]"),
                0.0,
            )
            / 100,
            "annualized_return_pct": BacktestingPyAdapter._finite_float(
                stats.get("Return (Ann.) [%]"),
                0.0,
            )
            / 100,
            "exposure_pct": BacktestingPyAdapter._finite_float(
                stats.get("Exposure Time [%]"),
                0.0,
            )
            / 100,
            "total_trades": len(trades),
            "winners": len(wins),
            "win_rate": len(wins) / len(trades) if trades else 0.0,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": abs(
                BacktestingPyAdapter._finite_float(
                    stats.get("Max. Drawdown [%]"),
                    0.0,
                )
                / 100
            ),
            "max_drawdown_duration": BacktestingPyAdapter._duration_text(
                stats.get("Max. Drawdown Duration")
            ),
            "sharpe_ratio": BacktestingPyAdapter._finite_float(
                stats.get("Sharpe Ratio"), 0.0
            ),
            "avg_trade_duration": BacktestingPyAdapter._duration_text(
                stats.get("Avg. Trade Duration")
            ),
            "commission_paid": sum(trade["commission"] for trade in trades),
            "avg_win": sum(wins) / len(wins) if wins else 0.0,
            "avg_loss": sum(losses) / len(losses) if losses else 0.0,
            "win_loss_ratio": (
                (sum(wins) / len(wins)) / abs(sum(losses) / len(losses))
                if wins and losses and sum(losses) != 0
                else 0.0
            ),
            "equity_curve": BacktestingPyAdapter._map_equity_curve(equity_frame),
            "drawdown_curve": BacktestingPyAdapter._map_drawdown_curve(equity_frame),
            "price_curve": BacktestingPyAdapter._map_price_curve(data, trades),
            "benchmark": BacktestingPyAdapter._benchmark(data, initial_cash),
            "trades": trades,
        }

    @staticmethod
    def _map_trade(row: pd.Series, config: dict[str, Any]) -> dict[str, Any]:
        direction = "long" if float(row["Size"]) > 0 else "short"
        exit_price = float(row["ExitPrice"])
        stop = BacktestingPyAdapter._optional_finite_float(row.get("SL"))
        target = BacktestingPyAdapter._optional_finite_float(row.get("TP"))
        if stop is not None and math.isclose(exit_price, stop, rel_tol=1e-9):
            entry_price = float(row["EntryPrice"])
            if config.get("breakeven_trigger_pct") and math.isclose(
                stop,
                entry_price,
                rel_tol=1e-9,
            ):
                exit_reason = "breakeven"
            else:
                fixed_stop_pct = config.get(
                    "stop_loss_pct",
                    config.get("stop_loss"),
                )
                fixed_stop = None
                if fixed_stop_pct:
                    direction_multiplier = -1 if direction == "long" else 1
                    fixed_stop = entry_price * (
                        1 + direction_multiplier * float(fixed_stop_pct) / 100
                    )
                if fixed_stop is not None and math.isclose(
                    stop,
                    fixed_stop,
                    rel_tol=1e-9,
                ):
                    exit_reason = "stop_loss"
                elif config.get("trailing_stop_pct"):
                    exit_reason = "trailing_stop"
                else:
                    exit_reason = "stop_loss"
        elif target is not None and math.isclose(exit_price, target, rel_tol=1e-9):
            exit_reason = "take_profit"
        elif (
            config.get("max_holding_bars")
            and int(row["ExitBar"]) - int(row["EntryBar"])
            >= int(config["max_holding_bars"])
        ):
            exit_reason = "time_exit"
        else:
            exit_reason = "condition_or_end"

        return {
            "direction": direction,
            "entry_time": BacktestingPyAdapter._iso_time(row["EntryTime"]),
            "exit_time": BacktestingPyAdapter._iso_time(row["ExitTime"]),
            "entry_price": float(row["EntryPrice"]),
            "exit_price": exit_price,
            "size": abs(float(row["Size"])),
            "pnl": float(row["PnL"]),
            "commission": float(row.get("Commission", 0.0) or 0.0),
            "return_pct": float(row["ReturnPct"]),
            "exit_reason": exit_reason,
        }

    @staticmethod
    def _map_equity_curve(
        equity_frame: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        if equity_frame.empty:
            return []

        frame = equity_frame
        if len(frame) > MAX_EQUITY_POINTS:
            indexes = np.linspace(0, len(frame) - 1, MAX_EQUITY_POINTS, dtype=int)
            frame = frame.iloc[np.unique(indexes)]

        return [
            {
                "time": BacktestingPyAdapter._iso_time(timestamp),
                "equity": float(row["Equity"]),
            }
            for timestamp, row in frame.iterrows()
        ]

    @staticmethod
    def _map_drawdown_curve(equity_frame: pd.DataFrame) -> list[dict[str, Any]]:
        if equity_frame.empty:
            return []
        frame = BacktestingPyAdapter._sample_frame(equity_frame)
        equity = frame["Equity"].astype(float)
        peaks = equity.cummax()
        return [
            {
                "time": BacktestingPyAdapter._iso_time(timestamp),
                "drawdown": float(peak - row["Equity"]),
                "drawdown_pct": (
                    float((peak - row["Equity"]) / peak) if peak else 0.0
                ),
            }
            for (timestamp, row), peak in zip(frame.iterrows(), peaks)
        ]

    @staticmethod
    def _map_price_curve(
        data: pd.DataFrame,
        trades: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        extra_times = [
            timestamp
            for trade in trades
            for timestamp in (trade["entry_time"], trade["exit_time"])
        ]
        frame = BacktestingPyAdapter._sample_frame(data, extra_times=extra_times)
        return [
            {
                "time": BacktestingPyAdapter._iso_time(timestamp),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
            }
            for timestamp, row in frame.iterrows()
        ]

    @staticmethod
    def _benchmark(data: pd.DataFrame, initial_cash: float) -> dict[str, float]:
        start = float(data["Close"].iloc[0])
        end = float(data["Close"].iloc[-1])
        return_pct = end / start - 1 if start else 0.0
        return {
            "start_price": start,
            "end_price": end,
            "return_pct": return_pct,
            "total_pnl": initial_cash * return_pct,
        }

    @staticmethod
    def _sample_frame(
        frame: pd.DataFrame,
        *,
        extra_times: list[str] | None = None,
    ) -> pd.DataFrame:
        if len(frame) <= MAX_EQUITY_POINTS:
            return frame
        indexes = np.linspace(0, len(frame) - 1, MAX_EQUITY_POINTS, dtype=int)
        if extra_times:
            targets = pd.to_datetime(extra_times, errors="coerce")
            for target in targets:
                if pd.isna(target):
                    continue
                matches = frame.index.get_indexer([target])
                if matches[0] >= 0:
                    indexes = np.append(indexes, matches[0])
        return frame.iloc[np.unique(indexes)]

    @staticmethod
    def _max_currency_drawdown(equity_frame: pd.DataFrame) -> float:
        if equity_frame.empty:
            return 0.0
        equity = equity_frame["Equity"].astype(float)
        return float((equity.cummax() - equity).max())

    @staticmethod
    def _duration_text(value: Any) -> str | None:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        return str(value)

    @staticmethod
    def _iso_time(value: Any) -> str:
        return value.isoformat() if hasattr(value, "isoformat") else str(value)

    @staticmethod
    def _positive_integer(value: Any, default: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        if parsed <= 0:
            raise ValueError("Indicator periods must be positive integers")
        return parsed

    @staticmethod
    def _optional_positive_integer(value: Any) -> int | None:
        if value in (None, ""):
            return None
        return BacktestingPyAdapter._positive_integer(value, 1)

    @staticmethod
    def _positive_number(value: Any, default: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = default
        if not math.isfinite(parsed) or parsed <= 0:
            raise ValueError("Numeric settings must be finite and positive")
        return parsed

    @staticmethod
    def _non_negative_number(value: Any, default: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = default
        if not math.isfinite(parsed) or parsed < 0:
            raise ValueError("Cost settings must be finite and non-negative")
        return parsed

    @staticmethod
    def _position_size(value: Any) -> float:
        parsed = BacktestingPyAdapter._positive_number(value, 1.0)
        if not (0 < parsed < 1 or parsed.is_integer()):
            raise ValueError("Position size must be a positive whole unit or a fraction below 1")
        return parsed

    @staticmethod
    def _optional_positive_number(value: Any) -> float | None:
        if value in (None, ""):
            return None
        parsed = float(value)
        if not math.isfinite(parsed) or parsed <= 0:
            raise ValueError("Stop loss and take profit must be positive")
        return parsed

    @staticmethod
    def _finite_float(value: Any, default: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        return parsed if math.isfinite(parsed) else default

    @staticmethod
    def _optional_finite_float(value: Any) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if math.isfinite(parsed) else None

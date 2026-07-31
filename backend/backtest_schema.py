"""Validated configuration and request models for the backtest module."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


BacktestStatus = Literal["queued", "running", "completed", "failed"]
ConditionOperator = Literal[
    ">",
    "<",
    "gt",
    "lt",
    ">=",
    "<=",
    "==",
    "cross_above",
    "cross_below",
]
ReferenceType = Literal[
    "value",
    "price",
    "ema",
    "sma",
    "rsi",
    "atr",
    "macd",
    "bollinger",
]

SUPPORTED_INTERVALS = {"1", "5", "15", "60", "240", "D", "W", "M"}


class StrategyReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ReferenceType
    params: dict[str, int | float | str] = Field(default_factory=dict)
    field: str | None = None
    value: float | None = None

    @model_validator(mode="after")
    def validate_reference(self) -> "StrategyReference":
        if self.type == "value":
            if self.value is None or not math.isfinite(self.value):
                raise ValueError("Value references require a finite numeric value")
            return self

        if self.type == "price":
            if (self.field or "close") not in {"open", "high", "low", "close"}:
                raise ValueError("Price field must be open, high, low, or close")
            return self

        if self.type in {"ema", "sma", "rsi", "atr", "bollinger"}:
            period = self.params.get("period", 14 if self.type in {"rsi", "atr"} else 20)
            if not isinstance(period, (int, float)) or int(period) <= 0:
                raise ValueError("Indicator periods must be positive integers")

        if self.type == "macd":
            fast = int(self.params.get("fast", 12))
            slow = int(self.params.get("slow", 26))
            signal = int(self.params.get("signal", 9))
            if min(fast, slow, signal) <= 0 or fast >= slow:
                raise ValueError("MACD periods must be positive and fast must be below slow")

        return self


class StrategyCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left: StrategyReference
    operator: ConditionOperator
    right: StrategyReference


class StrategyConditionGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator: Literal["and", "or"] = "and"
    conditions: list[StrategyCondition] = Field(default_factory=list)


class StrategyConfigModel(BaseModel):
    """Versioned strategy snapshot accepted by the backtest engine."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    symbol: str = "XAUUSD"
    series_id: str | None = None
    interval: str = "D"
    direction: Literal["long", "short"] = "long"
    entry_groups_operator: Literal["and", "or"] = "or"
    entry_groups: list[StrategyConditionGroup] = Field(default_factory=list)
    exit_groups_operator: Literal["and", "or"] = "or"
    exit_groups: list[StrategyConditionGroup] = Field(default_factory=list)
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    trailing_stop_pct: float | None = None
    breakeven_trigger_pct: float | None = None
    max_holding_bars: int | None = Field(default=None, ge=1, le=1_000_000)
    lookback_months: int = Field(default=6, ge=1, le=120)
    initial_cash: float = Field(default=100_000, gt=0)
    position_size: float = Field(default=1, gt=0)
    commission_bps: float = Field(default=0, ge=0)
    spread_bps: float = Field(default=0, ge=0)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        migrated = dict(value)
        migrated["schema_version"] = 2
        if "entry_groups" not in migrated:
            conditions = migrated.pop("entry_conditions", [])
            migrated["entry_groups"] = (
                [{"operator": "and", "conditions": conditions}]
                if conditions
                else []
            )
        else:
            migrated.pop("entry_conditions", None)
        if "exit_groups" not in migrated:
            conditions = migrated.pop("exit_conditions", [])
            migrated["exit_groups"] = (
                [{"operator": "and", "conditions": conditions}]
                if conditions
                else []
            )
        else:
            migrated.pop("exit_conditions", None)
        legacy_stop = migrated.pop("stop_loss", None)
        if "stop_loss_pct" not in migrated and legacy_stop is not None:
            migrated["stop_loss_pct"] = legacy_stop
        legacy_target = migrated.pop("take_profit", None)
        if "take_profit_pct" not in migrated and legacy_target is not None:
            migrated["take_profit_pct"] = legacy_target
        return migrated

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("A market symbol is required")
        return normalized

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, value: str) -> str:
        if value not in SUPPORTED_INTERVALS:
            raise ValueError(f"Unsupported timeframe: {value}")
        return value

    @field_validator(
        "stop_loss_pct",
        "take_profit_pct",
        "trailing_stop_pct",
        "breakeven_trigger_pct",
    )
    @classmethod
    def validate_optional_percent(cls, value: float | None) -> float | None:
        if value is not None and (not math.isfinite(value) or value <= 0):
            raise ValueError("Stop loss and take profit must be positive")
        return value

    @field_validator("initial_cash", "position_size", "commission_bps", "spread_bps")
    @classmethod
    def validate_finite_number(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Numeric settings must be finite")
        return value

    @field_validator("position_size")
    @classmethod
    def validate_position_size(cls, value: float) -> float:
        if not (0 < value < 1 or value.is_integer()):
            raise ValueError("Position size must be a positive whole unit or a fraction below 1")
        return value


def normalize_date_range(
    date_from: str | None,
    date_to: str | None,
) -> tuple[str | None, str | None]:
    """Validate ISO date inputs while preserving the caller's precision."""

    parsed_from = _parse_date(date_from)
    parsed_to = _parse_date(date_to)
    if parsed_from and parsed_to and parsed_from > parsed_to:
        raise ValueError("Start date must be before end date")
    return date_from, date_to


def _parse_date(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Backtest dates must use ISO 8601 format") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

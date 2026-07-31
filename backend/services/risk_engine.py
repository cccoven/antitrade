"""Deterministic position-risk calculations shared across trading workflows."""

from dataclasses import asdict, dataclass
import math
from typing import Any

from services.instruments import get_instrument_spec, normalize_instrument_symbol


@dataclass(frozen=True)
class PositionRiskInput:
    asset_class: str
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    account_size: float | None = None
    risk_percent: float | None = None
    risk_amount: float | None = None
    quantity: float | None = None
    target_price: float | None = None
    point_value: float | None = None


@dataclass(frozen=True)
class PositionRiskResult:
    asset_class: str
    symbol: str
    direction: str
    price_risk: float
    point_value: float | None
    unit_risk: float | None
    risk_budget: float | None
    quantity: float | None
    max_quantity: float | None
    risk_amount: float | None
    risk_percent: float | None
    reward_risk: float | None
    potential_reward: float | None
    instrument: dict[str, Any] | None
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["warnings"] = list(self.warnings)
        return data


def _positive(value: float | None, field: str) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"invalid_{field}")
    return number


def calculate_position_risk(data: PositionRiskInput) -> PositionRiskResult:
    """Calculate actual and budgeted risk through one stable interface.

    Quantity is derived from ``risk_amount`` or ``account_size * risk_percent``
    when it is not supplied. Futures quantities are rounded down to whole
    contracts. Unknown contract values stay explicit instead of being guessed.
    """

    asset_class = data.asset_class.strip().lower()
    direction = data.direction.strip().lower()
    if asset_class not in {"stock", "forex", "crypto", "futures"}:
        raise ValueError("unsupported_asset_class")
    if direction not in {"long", "short"}:
        raise ValueError("invalid_direction")

    entry_price = _positive(data.entry_price, "entry_price")
    stop_loss = _positive(data.stop_loss, "stop_loss")
    assert entry_price is not None and stop_loss is not None
    price_risk = abs(entry_price - stop_loss)
    if price_risk == 0:
        raise ValueError("zero_price_risk")

    account_size = _positive(data.account_size, "account_size")
    risk_percent_input = _positive(data.risk_percent, "risk_percent")
    risk_amount_input = _positive(data.risk_amount, "risk_amount")
    quantity_input = _positive(data.quantity, "quantity")
    point_value_override = _positive(data.point_value, "point_value")

    symbol = normalize_instrument_symbol(asset_class, data.symbol)
    if not symbol:
        raise ValueError("missing_symbol")
    instrument = get_instrument_spec(asset_class, symbol)
    resolved_point_value = point_value_override
    if resolved_point_value is None and instrument is not None:
        resolved_point_value = _positive(instrument.get("point_value"), "point_value")

    warnings: list[str] = []
    if resolved_point_value is None:
        warnings.append("point_value_required")
    if (direction == "long" and stop_loss >= entry_price) or (
        direction == "short" and stop_loss <= entry_price
    ):
        warnings.append("invalid_stop_structure")

    target_price = None
    if data.target_price is not None:
        target_price = _positive(data.target_price, "target_price")
        if target_price is not None and (
            (direction == "long" and target_price <= entry_price)
            or (direction == "short" and target_price >= entry_price)
        ):
            warnings.append("invalid_target_structure")

    tick_size = (instrument or {}).get("tick_size")
    if tick_size:
        prices = [entry_price, stop_loss]
        if target_price is not None:
            prices.append(target_price)
        if any(abs(value / tick_size - round(value / tick_size)) > 1e-8 for value in prices):
            warnings.append("price_not_tick_aligned")

    unit_risk = price_risk * resolved_point_value if resolved_point_value is not None else None
    risk_budget = risk_amount_input
    if risk_budget is None and account_size is not None and risk_percent_input is not None:
        risk_budget = account_size * risk_percent_input / 100

    max_quantity = None
    if unit_risk is not None and risk_budget is not None:
        max_quantity = risk_budget / unit_risk
        if asset_class == "futures":
            max_quantity = math.floor(max_quantity)

    quantity = quantity_input if quantity_input is not None else max_quantity
    actual_risk_amount = unit_risk * quantity if unit_risk is not None and quantity is not None else None
    actual_risk_percent = (
        actual_risk_amount / account_size * 100
        if actual_risk_amount is not None and account_size is not None
        else None
    )

    reward_risk = None
    potential_reward = None
    if target_price is not None:
        reward_distance = (
            target_price - entry_price if direction == "long" else entry_price - target_price
        )
        reward_risk = reward_distance / price_risk
        if quantity is not None and resolved_point_value is not None:
            potential_reward = reward_distance * quantity * resolved_point_value

    return PositionRiskResult(
        asset_class=asset_class,
        symbol=symbol,
        direction=direction,
        price_risk=price_risk,
        point_value=resolved_point_value,
        unit_risk=unit_risk,
        risk_budget=risk_budget,
        quantity=quantity,
        max_quantity=max_quantity,
        risk_amount=actual_risk_amount,
        risk_percent=actual_risk_percent,
        reward_risk=reward_risk,
        potential_reward=potential_reward,
        instrument=instrument,
        warnings=tuple(dict.fromkeys(warnings)),
    )

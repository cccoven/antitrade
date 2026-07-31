"""Small, explicit instrument registry for calculations that need contract metadata."""

from typing import Any

from services.market_gateway import FUTURES_CONTRACT_SPECS


# Calculation-only compatibility view. Provider mappings live in the gateway catalog.
FUTURES_SPECS: dict[str, dict[str, Any]] = {
    symbol: {
        "symbol": symbol,
        "currency": spec.currency,
        "tick_size": spec.tick_size,
        "tick_value": spec.tick_value,
        "point_value": spec.point_value,
        "timezone": spec.timezone,
    }
    for symbol, spec in FUTURES_CONTRACT_SPECS.items()
}


def normalize_instrument_symbol(asset_class: str, symbol: str) -> str:
    value = symbol.strip().upper().replace(" ", "")
    if asset_class == "futures" and value.endswith("1!"):
        value = value[:-2]
    return value


def get_instrument_spec(asset_class: str, symbol: str) -> dict[str, Any] | None:
    normalized = normalize_instrument_symbol(asset_class, symbol)
    if asset_class == "futures":
        spec = FUTURES_SPECS.get(normalized)
        return dict(spec) if spec else None
    if asset_class in {"stock", "crypto"}:
        return {
            "symbol": normalized,
            "point_value": 1.0,
        }
    return None


def position_risk_amount(
    asset_class: str, symbol: str, entry_price: float, stop_loss: float, quantity: float,
) -> float | None:
    """Compatibility wrapper around the shared risk engine."""
    from services.risk_engine import PositionRiskInput, calculate_position_risk

    try:
        result = calculate_position_risk(PositionRiskInput(
            asset_class=asset_class,
            symbol=symbol,
            direction="long" if stop_loss < entry_price else "short",
            entry_price=entry_price,
            stop_loss=stop_loss,
            quantity=quantity,
        ))
    except ValueError:
        return None
    return result.risk_amount

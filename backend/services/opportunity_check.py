"""Deterministic, user-scoped market opportunity and rule compliance checks."""

from typing import Any

from sqlalchemy.orm import Session

from services.instruments import get_instrument_spec
from services.journal import JournalService
from services.market_research import get_market_snapshot
from services.risk_engine import PositionRiskInput, calculate_position_risk


SUPPORTED_MARKETS = {"stock", "forex", "crypto", "futures"}
SUPPORTED_DIRECTIONS = {"long", "short"}


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _plan_differences(plan: dict | None, data: dict) -> dict | None:
    if plan is None:
        return None
    differences: dict[str, float | None] = {}
    for field in ("entry_price", "stop_loss", "target_price"):
        current = _number(data.get(field))
        planned = _number(plan.get(field))
        differences[field] = current - planned if current is not None and planned is not None else None
    return differences


def check_trade_opportunity(
    session: Session,
    user_id: str,
    *,
    market: str | None = None,
    symbol: str | None = None,
    direction: str | None = None,
    entry_price: float | None = None,
    stop_loss: float | None = None,
    target_price: float | None = None,
    quantity: float | None = None,
    interval: str = "1day",
    account_size: float | None = None,
    plan_id: str | None = None,
    strategy_id: str | None = None,
    setup_type: str | None = None,
    confidence: int | None = None,
    thesis: str = "",
    snapshot: dict | None = None,
) -> dict:
    journal = JournalService(session)
    requested_symbol = (symbol or "").strip().upper()
    requested_direction = (direction or "").strip().lower()
    plan = journal.find_matching_trade_plan(
        user_id, requested_symbol, requested_direction, plan_id=plan_id,
    )
    if plan_id and plan is None:
        return {"error": "plan_not_found"}

    resolved_market = (market or (plan or {}).get("market") or "").strip().lower()
    resolved_symbol = requested_symbol or str((plan or {}).get("symbol") or "").strip().upper()
    resolved_direction = requested_direction or str((plan or {}).get("direction") or "").strip().lower()
    if resolved_market not in SUPPORTED_MARKETS:
        return {"error": "unsupported_asset_class"}
    if not resolved_symbol:
        return {"error": "missing_symbol"}
    if resolved_direction not in SUPPORTED_DIRECTIONS:
        return {"error": "invalid_direction"}

    resolved_entry = _number(entry_price if entry_price is not None else (plan or {}).get("entry_price"))
    resolved_stop = _number(stop_loss if stop_loss is not None else (plan or {}).get("stop_loss"))
    resolved_target = _number(target_price if target_price is not None else (plan or {}).get("target_price"))
    resolved_quantity = _number(quantity if quantity is not None else (plan or {}).get("quantity"))
    resolved_account_size = _number(
        account_size if account_size is not None else (plan or {}).get("account_size")
    )
    if resolved_account_size is None:
        resolved_account_size = journal.get_starting_capital(user_id=user_id)

    market_snapshot = snapshot or get_market_snapshot(
        resolved_market, resolved_symbol, interval,
    )
    normalized_symbol = str(market_snapshot.get("symbol") or resolved_symbol)
    quote_price = _number((market_snapshot.get("quote") or {}).get("price"))
    instrument_spec = get_instrument_spec(resolved_market, normalized_symbol)

    unit_risk = None
    risk_amount = None
    risk_percent = None
    reward_risk = None
    risk_warnings: list[str] = []
    if resolved_entry is not None and resolved_stop is not None:
        try:
            risk_result = calculate_position_risk(PositionRiskInput(
                asset_class=resolved_market,
                symbol=normalized_symbol,
                direction=resolved_direction,
                entry_price=resolved_entry,
                stop_loss=resolved_stop,
                target_price=resolved_target,
                quantity=resolved_quantity,
                account_size=resolved_account_size,
            ))
            instrument_spec = risk_result.instrument
            unit_risk = risk_result.unit_risk
            risk_amount = risk_result.risk_amount
            risk_percent = risk_result.risk_percent
            reward_risk = risk_result.reward_risk
            risk_warnings.extend(risk_result.warnings)
        except ValueError as exc:
            risk_warnings.append(str(exc))

    active_rules = journal.list_rules(user_id, active_only=True)
    max_risk_thresholds = [
        _number(rule.get("threshold"))
        for rule in active_rules if rule.get("rule_type") == "max_risk_percent"
    ]
    max_risk_thresholds = [value for value in max_risk_thresholds if value is not None]
    max_quantity = None
    if resolved_account_size and resolved_entry is not None and resolved_stop is not None and max_risk_thresholds:
        try:
            max_quantity = calculate_position_risk(PositionRiskInput(
                asset_class=resolved_market,
                symbol=normalized_symbol,
                direction=resolved_direction,
                entry_price=resolved_entry,
                stop_loss=resolved_stop,
                account_size=resolved_account_size,
                risk_percent=min(max_risk_thresholds),
            )).max_quantity
        except ValueError:
            max_quantity = None

    compliance_input = {
        "market": resolved_market,
        "symbol": normalized_symbol,
        "direction": resolved_direction,
        "entry_price": resolved_entry,
        "stop_loss": resolved_stop,
        "target_price": resolved_target,
        "quantity": resolved_quantity,
        "account_size": resolved_account_size,
        "plan_id": plan.get("id") if plan else None,
        "strategy_id": strategy_id or (plan or {}).get("strategy_id"),
        "confidence": confidence,
        "thesis": thesis or (plan or {}).get("thesis") or "",
    }
    compliance = journal.evaluate_compliance(user_id, compliance_input)
    history = journal.get_similar_trade_stats(
        user_id,
        normalized_symbol,
        resolved_direction,
        strategy_id=strategy_id or (plan or {}).get("strategy_id"),
        setup_type=setup_type,
    )

    warnings: list[str] = []
    if market_snapshot.get("error"):
        warnings.append(str(market_snapshot["error"]))
    if resolved_entry is None or resolved_stop is None:
        warnings.append("risk_inputs_incomplete")
    if resolved_quantity is None:
        warnings.append("quantity_missing")
    if instrument_spec is None:
        warnings.append("instrument_spec_unavailable")
    if history["sample_quality"] == "insufficient":
        warnings.append("history_sample_insufficient")
    if not active_rules:
        warnings.append("no_active_rules")
    invalid_price_structure = any(
        item in risk_warnings for item in ("invalid_stop_structure", "invalid_target_structure")
    )
    price_not_tick_aligned = "price_not_tick_aligned" in risk_warnings
    warnings.extend(
        item for item in risk_warnings
        if item not in {"point_value_required", "invalid_stop_structure", "invalid_target_structure"}
    )
    if invalid_price_structure:
        warnings.append("invalid_price_structure")

    critical_failed = any(
        result["weight"] == "critical" and result["status"] == "failed"
        for result in compliance["results"]
    )
    critical_unknown = any(
        result["weight"] == "critical" and result["status"] == "not_applicable"
        for result in compliance["results"]
    )
    if (
        market_snapshot.get("error")
        or resolved_entry is None
        or resolved_stop is None
        or resolved_quantity is None
        or critical_unknown
        or not active_rules
    ):
        verdict = "insufficient_data"
    elif critical_failed or compliance["failed"] > 0 or invalid_price_structure or price_not_tick_aligned:
        verdict = "adjust"
    else:
        verdict = "compliant"

    entry_deviation = quote_price - resolved_entry if quote_price is not None and resolved_entry is not None else None
    entry_deviation_percent = (
        entry_deviation / resolved_entry * 100
        if entry_deviation is not None and resolved_entry not in (None, 0) else None
    )
    return {
        "verdict": verdict,
        "market": market_snapshot,
        "opportunity": {
            "market": resolved_market,
            "symbol": normalized_symbol,
            "direction": resolved_direction,
            "interval": interval,
            "entry_price": resolved_entry,
            "stop_loss": resolved_stop,
            "target_price": resolved_target,
            "quantity": resolved_quantity,
            "current_price": quote_price,
            "entry_deviation": entry_deviation,
            "entry_deviation_percent": entry_deviation_percent,
        },
        "risk": {
            "account_size": resolved_account_size,
            "unit_risk": unit_risk,
            "risk_amount": risk_amount,
            "risk_percent": risk_percent,
            "reward_risk": reward_risk,
            "max_quantity": max_quantity,
        },
        "instrument": instrument_spec,
        "plan_match": {
            "plan": plan,
            "differences": _plan_differences(plan, compliance_input),
        } if plan else None,
        "compliance": compliance,
        "history": history,
        "warnings": list(dict.fromkeys(warnings)),
    }

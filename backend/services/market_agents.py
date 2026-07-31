"""Deterministic market-watching workflows for automation tasks."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import AutomationTask, TradePlan
from services.automation import WorkflowFinding, WorkflowResult
from services.automation_analysis import (
    generate_report_analysis,
    normalize_analysis_instruction,
)
from services.instruments import FUTURES_SPECS
from services.market_research import get_economic_calendar, get_market_snapshot
from services.notifications import parse_utc, utc_iso

UTC = timezone.utc
SUPPORTED_INTERVALS = {"5min", "15min", "1h", "4h", "1day"}
SUPPORTED_CONDITIONS = {"percent_change", "price_above", "price_below"}


def _asset_class(symbol: str, configured: str | None = None) -> str:
    if configured in {"stock", "forex", "crypto", "futures"}:
        return configured
    compact = symbol.strip().upper().replace("/", "").replace("-", "")
    if compact in FUTURES_SPECS or compact.removesuffix("1!") in FUTURES_SPECS:
        return "futures"
    if compact.startswith(("BTC", "ETH", "SOL", "XRP", "DOGE")):
        return "crypto"
    if len(compact) == 6 and compact.isalpha():
        return "forex"
    return "stock"


def _symbols(task: AutomationTask) -> list[str]:
    values = (task.scope or {}).get("symbols", [])
    return list(dict.fromkeys(
        str(value).strip().upper() for value in values if str(value).strip()
    ))[:20]


def _interval(task: AutomationTask) -> str:
    value = str((task.scope or {}).get("interval") or "1h")
    return value if value in SUPPORTED_INTERVALS else "1h"


def _market_rows(task: AutomationTask) -> list[dict[str, Any]]:
    configured_asset_class = (task.scope or {}).get("asset_class")
    rows: list[dict[str, Any]] = []
    for symbol in _symbols(task):
        asset_class = _asset_class(symbol, configured_asset_class)
        snapshot = get_market_snapshot(asset_class, symbol, _interval(task))
        quote = snapshot.get("quote") if isinstance(snapshot.get("quote"), dict) else {}
        candles = (
            snapshot.get("recent_candles")
            if isinstance(snapshot.get("recent_candles"), list)
            else []
        )
        latest_close = _number(candles[0].get("close")) if candles else None
        previous_close = _number(candles[1].get("close")) if len(candles) > 1 else None
        interval_change = (
            (latest_close - previous_close) / previous_close * 100
            if latest_close is not None and previous_close not in (None, 0)
            else None
        )
        rows.append({
            "kind": "market_snapshot",
            "symbol": str(snapshot.get("symbol") or symbol),
            "asset_class": asset_class,
            "price": quote.get("price"),
            "percent_change": (
                interval_change
                if interval_change is not None
                else quote.get("percent_change")
            ),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "volume": quote.get("volume"),
            "technicals": snapshot.get("technicals") or {},
            "provider": snapshot.get("provider"),
            "as_of": snapshot.get("as_of"),
            "error": snapshot.get("error"),
        })
    return rows


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _quote_summary(rows: list[dict[str, Any]], *, english: bool = False) -> str:
    parts = []
    for row in rows:
        price = _number(row.get("price"))
        change = _number(row.get("percent_change"))
        if price is None:
            continue
        change_text = f"{change:+.2f}%" if change is not None else "—"
        parts.append(f"{row['symbol']} {price:g} ({change_text})")
    if not parts:
        return (
            "Market data is temporarily unavailable for the selected symbols."
            if english else "所选品种的行情数据暂时不可用。"
        )
    prefix = "Market snapshot: " if english else "行情快照："
    return prefix + "；".join(parts)


def _apply_analysis(
    task: AutomationTask,
    result: WorkflowResult,
) -> WorkflowResult:
    instruction = normalize_analysis_instruction(
        task.task_type,
        (task.scope or {}).get("analysis_instruction"),
    )
    if not instruction:
        return result
    analysis = generate_report_analysis(
        task_type=task.task_type,
        instruction=instruction,
        baseline_zh=result.summary,
        baseline_en=result.summary_en,
        evidence=result.evidence,
    )
    metadata = {
        "instruction": instruction,
        "status": "applied" if analysis is not None else "fallback",
        "model": analysis.model if analysis is not None else "rule",
    }
    if analysis is None:
        return replace(result, analysis=metadata)
    return replace(
        result,
        summary=analysis.summary,
        summary_en=analysis.summary_en,
        analysis=metadata,
    )


def run_market_watch(
    session: Session,
    task: AutomationTask,
    as_of: datetime,
) -> WorkflowResult:
    del session
    current = as_of if as_of.tzinfo else as_of.replace(tzinfo=UTC)
    if not _symbols(task):
        return WorkflowResult(
            summary="尚未配置关注品种。",
            summary_en="No symbols are configured.",
            status="skipped",
            output_kind="report",
            as_of=utc_iso(current),
        )
    rows = _market_rows(task)
    available = [row for row in rows if row.get("price") is not None]
    result = WorkflowResult(
        summary=_quote_summary(rows),
        summary_en=_quote_summary(rows, english=True),
        evidence=tuple(rows),
        metrics={
            "symbol_count": len(rows),
            "available_count": len(available),
            "unavailable_count": len(rows) - len(available),
        },
        status="succeeded" if len(available) == len(rows) else "partial",
        output_kind="report",
        as_of=utc_iso(current),
    )
    return _apply_analysis(task, result)


def run_session_report(
    session: Session,
    task: AutomationTask,
    as_of: datetime,
) -> WorkflowResult:
    del session
    current = as_of if as_of.tzinfo else as_of.replace(tzinfo=UTC)
    rows = _market_rows(task)
    available = [row for row in rows if row.get("price") is not None]
    calendar = get_economic_calendar()
    upcoming: list[dict[str, Any]] = []
    for item in calendar.get("items", []):
        event_time = parse_utc(item.get("date"))
        if event_time is not None and current <= event_time <= current + timedelta(hours=24):
            upcoming.append({
                "kind": "economic_event",
                "title": item.get("title"),
                "currency": item.get("currency"),
                "impact": item.get("impact"),
                "date": item.get("date"),
            })
    market_zh = _quote_summary(rows)
    market_en = _quote_summary(rows, english=True)
    summary = f"{market_zh}；未来 24 小时有 {len(upcoming)} 个重要经济事件。"
    summary_en = f"{market_en}; {len(upcoming)} significant economic events are due in the next 24 hours."
    has_calendar = not calendar.get("error")
    status = "succeeded" if len(available) == len(rows) and has_calendar else "partial"
    result = WorkflowResult(
        summary=summary,
        summary_en=summary_en,
        evidence=tuple([*rows, *upcoming]),
        metrics={
            "symbol_count": len(rows),
            "available_count": len(available),
            "upcoming_event_count": len(upcoming),
        },
        status=status,
        output_kind="report",
        as_of=utc_iso(current),
    )
    return _apply_analysis(task, result)


def run_condition_monitor(
    session: Session,
    task: AutomationTask,
    as_of: datetime,
) -> WorkflowResult:
    del session
    current = as_of if as_of.tzinfo else as_of.replace(tzinfo=UTC)
    scope = task.scope or {}
    condition = str(scope.get("condition_kind") or "percent_change")
    threshold = _number(scope.get("threshold"))
    rows = _market_rows(task)
    findings: list[WorkflowFinding] = []
    if condition not in SUPPORTED_CONDITIONS or threshold is None:
        return WorkflowResult(
            summary="监控条件配置无效。",
            summary_en="The monitoring condition is invalid.",
            status="skipped",
            as_of=utc_iso(current),
        )

    for row in rows:
        symbol = str(row["symbol"])
        price = _number(row.get("price"))
        change = _number(row.get("percent_change"))
        matched = False
        value: float | None = None
        if condition == "percent_change" and change is not None:
            value = abs(change)
            matched = value >= threshold
            title = f"{symbol} 波动达到监控条件"
            title_en = f"{symbol} reached the movement threshold"
            body = f"当前涨跌幅为 {change:+.2f}%，监控阈值为 {threshold:.2f}%。"
            body_en = f"The current move is {change:+.2f}%; the threshold is {threshold:.2f}%."
        elif condition == "price_above" and price is not None:
            value = price
            matched = price >= threshold
            title = f"{symbol} 已升至目标价位上方"
            title_en = f"{symbol} moved above the target level"
            body = f"当前价格为 {price:g}，监控价位为 {threshold:g}。"
            body_en = f"The current price is {price:g}; the monitored level is {threshold:g}."
        elif condition == "price_below" and price is not None:
            value = price
            matched = price <= threshold
            title = f"{symbol} 已降至目标价位下方"
            title_en = f"{symbol} moved below the target level"
            body = f"当前价格为 {price:g}，监控价位为 {threshold:g}。"
            body_en = f"The current price is {price:g}; the monitored level is {threshold:g}."
        else:
            continue
        if not matched:
            continue
        severe_move = condition == "percent_change" and value is not None and value >= threshold * 2
        findings.append(WorkflowFinding(
            finding_type="market",
            severity="critical" if severe_move else "warning",
            fingerprint=f"market:{condition}:{symbol}",
            title=title,
            body=body,
            title_en=title_en,
            body_en=body_en,
            subject_type="symbol",
            subject_id=symbol,
            evidence=(row,),
            payload={
                "condition_kind": condition,
                "threshold": threshold,
                "current": value,
                "symbol": symbol,
            },
        ))
    return WorkflowResult(
        summary=f"检查 {len(rows)} 个品种，发现 {len(findings)} 个条件已触发。",
        summary_en=f"Checked {len(rows)} symbols; {len(findings)} conditions were triggered.",
        findings=tuple(findings),
        evidence=tuple(rows),
        metrics={"symbol_count": len(rows), "triggered_count": len(findings)},
        status="partial" if rows and all(row.get("price") is None for row in rows) else "succeeded",
        as_of=utc_iso(current),
    )


def run_plan_guardian(
    session: Session,
    task: AutomationTask,
    as_of: datetime,
) -> WorkflowResult:
    current = as_of if as_of.tzinfo else as_of.replace(tzinfo=UTC)
    plans = session.execute(
        select(TradePlan).where(
            TradePlan.user_id == task.user_id,
            TradePlan.status == "active",
        )
    ).scalars().all()
    proximity = _number((task.scope or {}).get("proximity_percent")) or 0.5
    findings: list[WorkflowFinding] = []
    evidence: list[dict[str, Any]] = []
    available = 0
    for plan in plans[:20]:
        snapshot = get_market_snapshot(_asset_class(plan.symbol, plan.market), plan.symbol, _interval(task))
        quote = snapshot.get("quote") if isinstance(snapshot.get("quote"), dict) else {}
        price = _number(quote.get("price"))
        row = {
            "kind": "plan_market_snapshot",
            "plan_id": plan.id,
            "symbol": plan.symbol,
            "price": price,
            "entry_price": plan.entry_price,
            "target_price": plan.target_price,
            "stop_loss": plan.stop_loss,
            "direction": plan.direction,
            "as_of": snapshot.get("as_of"),
            "provider": snapshot.get("provider"),
            "error": snapshot.get("error"),
        }
        evidence.append(row)
        if price is None:
            continue
        available += 1
        stop_hit = (
            plan.direction == "long" and price <= plan.stop_loss
        ) or (
            plan.direction == "short" and price >= plan.stop_loss
        )
        target_hit = plan.target_price is not None and (
            (plan.direction == "long" and price >= plan.target_price)
            or (plan.direction == "short" and price <= plan.target_price)
        )
        distance = abs(price - plan.entry_price) / plan.entry_price * 100
        if stop_hit:
            findings.append(WorkflowFinding(
                finding_type="plan",
                severity="critical",
                fingerprint=f"plan:stop:{plan.id}",
                title=f"{plan.symbol} 计划失效价已触发",
                body=f"当前价格 {price:g}，计划止损/失效价为 {plan.stop_loss:g}。",
                title_en=f"{plan.symbol} plan invalidation level was reached",
                body_en=f"The current price is {price:g}; the plan stop/invalidation level is {plan.stop_loss:g}.",
                subject_type="plan",
                subject_id=plan.id,
                evidence=(row,),
                payload={"condition": "stop", "current": price, "threshold": plan.stop_loss},
            ))
        elif target_hit:
            findings.append(WorkflowFinding(
                finding_type="plan",
                severity="info",
                fingerprint=f"plan:target:{plan.id}",
                title=f"{plan.symbol} 计划目标价已触达",
                body=f"当前价格 {price:g}，计划目标价为 {plan.target_price:g}。",
                title_en=f"{plan.symbol} plan target was reached",
                body_en=f"The current price is {price:g}; the plan target is {plan.target_price:g}.",
                subject_type="plan",
                subject_id=plan.id,
                evidence=(row,),
                payload={"condition": "target", "current": price, "threshold": plan.target_price},
            ))
        elif distance <= proximity:
            findings.append(WorkflowFinding(
                finding_type="plan",
                severity="warning",
                fingerprint=f"plan:entry:{plan.id}",
                title=f"{plan.symbol} 接近计划入场价",
                body=f"当前价格 {price:g}，距离计划入场价 {plan.entry_price:g} 约 {distance:.2f}%。",
                title_en=f"{plan.symbol} is near the planned entry",
                body_en=f"The current price is {price:g}, about {distance:.2f}% from the planned entry at {plan.entry_price:g}.",
                subject_type="plan",
                subject_id=plan.id,
                evidence=(row,),
                payload={"condition": "entry", "current": price, "distance_percent": distance},
            ))
    return WorkflowResult(
        summary=f"检查 {len(plans)} 个活跃交易计划，发现 {len(findings)} 个需要关注的变化。",
        summary_en=f"Checked {len(plans)} active trade plans; {len(findings)} changes need attention.",
        findings=tuple(findings),
        evidence=tuple(evidence),
        metrics={
            "active_plan_count": len(plans),
            "available_count": available,
            "triggered_count": len(findings),
        },
        status="partial" if plans and available < len(plans[:20]) else "succeeded",
        as_of=utc_iso(current),
    )

"""Bounded news-to-user-context impact assessment."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import AutomationRun, AutomationTask, FeedItem, Trade, TradePlan
from services.automation import WorkflowFinding, WorkflowResult
from services.market_data_runtime import get_market_data_gateway
from services.market_gateway import InstrumentSearch
from services.notifications import parse_utc, utc_iso

UTC = timezone.utc
_MACRO_SENSITIVE = (
    "NQ", "MNQ", "ES", "MES", "SPX", "NDX", "GC", "MGC", "XAU",
    "EUR", "GBP", "JPY", "USD",
)


def _compact_symbol(value: str) -> str:
    text = value.strip().upper()
    if ":" in text:
        text = text.split(":", 1)[1]
    return re.sub(r"[^A-Z0-9]", "", text).removesuffix("1")


def _subject_symbol(symbol: str, subject_type: str, subject_id: str) -> dict:
    instrument = get_market_data_gateway().resolve_instrument(
        InstrumentSearch(text=symbol),
    )
    return {
        "symbol": _compact_symbol(
            instrument.display_symbol if instrument is not None else symbol,
        ),
        "instrument_id": instrument.id if instrument is not None else None,
        "raw_symbol": symbol,
        "subject_type": subject_type,
        "subject_id": subject_id,
    }


def _matches(item: FeedItem, subject: dict) -> bool:
    symbol = subject["symbol"]
    canonical_tags = set(item.symbols or [])
    if subject["instrument_id"] in canonical_tags:
        return True
    tagged = {
        _compact_symbol(value)
        for value in canonical_tags
        if not value.startswith("instrument:")
    }
    if symbol in tagged:
        return True
    haystack = f"{item.title} {item.summary}".upper()
    if re.search(rf"(?<![A-Z0-9]){re.escape(symbol)}(?![A-Z0-9])", haystack):
        return True
    return item.category == "macro" and symbol.startswith(_MACRO_SENSITIVE)


def run_news_impact(
    session: Session,
    task: AutomationTask,
    as_of: datetime,
) -> WorkflowResult:
    current = as_of if as_of.tzinfo else as_of.replace(tzinfo=UTC)
    open_trades = session.execute(
        select(Trade).where(
            Trade.user_id == task.user_id,
            Trade.position_status == "open",
        )
    ).scalars().all()
    plans = session.execute(
        select(TradePlan).where(
            TradePlan.user_id == task.user_id,
            TradePlan.status == "active",
        )
    ).scalars().all()
    subjects = [
        _subject_symbol(trade.symbol, "trade", trade.id) for trade in open_trades
    ]
    subjects.extend(
        _subject_symbol(plan.symbol, "plan", plan.id) for plan in plans
    )
    subjects.extend(
        _subject_symbol(str(symbol), "watch", _compact_symbol(str(symbol)))
        for symbol in (task.scope or {}).get("symbols", [])
        if str(symbol).strip()
    )
    unique_subjects = {
        (item["subject_type"], item["subject_id"], item["symbol"]): item
        for item in subjects
    }
    subjects = list(unique_subjects.values())
    if not subjects:
        return WorkflowResult(
            summary="没有未平仓交易、活跃计划或关注品种。",
            status="skipped",
            as_of=utc_iso(current),
        )

    last_success = session.execute(
        select(AutomationRun)
        .where(
            AutomationRun.task_id == task.id,
            AutomationRun.status.in_(("succeeded", "partial")),
            AutomationRun.finished_at.isnot(None),
        )
        .order_by(AutomationRun.finished_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    since = (
        parse_utc(last_success.finished_at)
        if last_success and last_success.finished_at
        else current - timedelta(hours=6)
    )
    since_value = utc_iso(since)
    items = session.execute(
        select(FeedItem)
        .where(func.coalesce(FeedItem.published_at, FeedItem.fetched_at) > since_value)
        .order_by(func.coalesce(FeedItem.published_at, FeedItem.fetched_at).desc())
        .limit(40)
    ).scalars().all()

    findings: list[WorkflowFinding] = []
    matched_item_ids: set[str] = set()
    for item in items:
        for subject in subjects:
            if not _matches(item, subject):
                continue
            matched_item_ids.add(item.id)
            published = item.published_at or item.fetched_at
            findings.append(WorkflowFinding(
                finding_type="news",
                severity="warning" if item.category == "macro" else "info",
                fingerprint=(
                    f"news:{item.id}:{subject['subject_type']}:{subject['subject_id']}"
                ),
                title=f"{subject['raw_symbol']} 出现相关资讯",
                body=f"{item.title}。请核对现有计划的前提和失效条件。",
                title_en=f"Relevant news for {subject['raw_symbol']}",
                body_en=(
                    f"{item.title}. Review the assumptions and invalidation "
                    "conditions in the current plan."
                ),
                subject_type=subject["subject_type"],
                subject_id=subject["subject_id"],
                evidence=({
                    "kind": "feed_item",
                    "id": item.id,
                    "title": item.title,
                    "url": item.url,
                    "source_key": item.source_key,
                    "published_at": item.published_at,
                    "fetched_at": item.fetched_at,
                    "assessed_at": utc_iso(current),
                },),
                payload={
                    "materiality": "watch",
                    "direction": "unknown",
                    "horizon": "unknown",
                    "confidence": 0.55,
                    "symbol": subject["raw_symbol"],
                    "category": item.category,
                    "source_id": item.id,
                },
                expires_at=utc_iso(current + timedelta(days=2)),
            ))

    return WorkflowResult(
        summary=(
            f"发现 {len(findings)} 条与当前交易上下文相关的资讯影响。"
            if findings else "没有发现与当前交易上下文直接相关的新资讯。"
        ),
        findings=tuple(findings),
        evidence=tuple(
            {"kind": "feed_item", "id": item_id} for item_id in sorted(matched_item_ids)
        ),
        metrics={
            "candidate_count": len(items),
            "matched_item_count": len(matched_item_ids),
            "affected_subject_count": len({
                (finding.subject_type, finding.subject_id) for finding in findings
            }),
        },
        as_of=utc_iso(current),
    )

"""Deterministic account-level risk checks for automation tasks."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import AutomationTask, JournalSettings, Trade, TradePlan, TradingRule
from services.automation import WorkflowFinding, WorkflowResult
from services.instruments import FUTURES_SPECS, position_risk_amount
from services.notifications import utc_iso

UTC = timezone.utc
WEIGHT_SEVERITY = {
    "critical": "critical",
    "important": "warning",
    "nice_to_have": "info",
}


def _asset_class(symbol: str) -> str:
    compact = symbol.strip().upper().replace("/", "").replace("-", "")
    if compact in FUTURES_SPECS:
        return "futures"
    if compact.startswith(("BTC", "ETH", "SOL")):
        return "crypto"
    if len(compact) == 6 and compact.isalpha():
        return "forex"
    return "stock"


def _severity(rule: TradingRule) -> str:
    return WEIGHT_SEVERITY.get(rule.weight, "warning")


def _finding(
    rule: TradingRule,
    *,
    current: float,
    threshold: float,
    title: str,
    body: str,
    title_en: str,
    body_en: str,
    subject_type: str = "account",
    subject_id: str = "",
    evidence: tuple[dict, ...] = (),
) -> WorkflowFinding:
    return WorkflowFinding(
        finding_type="risk",
        severity=_severity(rule),
        fingerprint=f"risk:{rule.rule_type}:{subject_type}:{subject_id or 'all'}",
        title=title,
        body=body,
        title_en=title_en,
        body_en=body_en,
        subject_type=subject_type,
        subject_id=subject_id,
        evidence=evidence,
        payload={
            "rule_id": rule.id,
            "rule_type": rule.rule_type,
            "current": current,
            "threshold": threshold,
        },
    )


def run_risk_guardian(
    session: Session,
    task: AutomationTask,
    as_of: datetime,
) -> WorkflowResult:
    current = as_of if as_of.tzinfo else as_of.replace(tzinfo=UTC)
    zone = ZoneInfo(task.timezone)
    local_date = current.astimezone(zone).date()

    trades = session.execute(
        select(Trade)
        .where(Trade.user_id == task.user_id)
        .order_by(Trade.close_time.desc().nullslast(), Trade.open_time.desc().nullslast())
    ).scalars().all()
    plans = session.execute(
        select(TradePlan).where(
            TradePlan.user_id == task.user_id,
            TradePlan.status == "active",
        )
    ).scalars().all()
    rules = session.execute(
        select(TradingRule).where(
            TradingRule.user_id == task.user_id,
            TradingRule.active == 1,
        )
    ).scalars().all()
    settings = session.get(JournalSettings, task.user_id)
    starting_capital = float(settings.starting_capital) if settings and settings.starting_capital else None

    def local_day(value: str | None):
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(zone).date()

    todays_opened = [trade for trade in trades if local_day(trade.open_time) == local_date]
    todays_closed = [trade for trade in trades if local_day(trade.close_time) == local_date]
    daily_realized = sum(float(trade.pnl or 0) for trade in todays_closed)
    daily_loss = abs(min(daily_realized, 0.0))

    open_trades = [
        trade for trade in trades
        if trade.position_status == "open"
    ]
    open_risk = 0.0
    unknown_open_risk: list[Trade] = []
    for trade in open_trades:
        if None in (trade.open_price, trade.stop_loss, trade.quantity):
            unknown_open_risk.append(trade)
            continue
        amount = position_risk_amount(
            _asset_class(trade.symbol),
            trade.symbol,
            float(trade.open_price),
            float(trade.stop_loss),
            float(trade.quantity),
        )
        if amount is None:
            unknown_open_risk.append(trade)
        else:
            open_risk += amount

    plan_risk = sum(
        float(plan.account_size) * float(plan.risk_percent) / 100
        for plan in plans
    )
    total_exposure = open_risk + plan_risk

    closed_pnls = [
        float(trade.pnl)
        for trade in trades
        if trade.pnl is not None and trade.close_time is not None
    ]
    consecutive_losses = 0
    for pnl in closed_pnls:
        if pnl < 0:
            consecutive_losses += 1
        elif pnl > 0:
            break

    findings: list[WorkflowFinding] = []
    evidence_base = ({
        "kind": "risk_snapshot",
        "as_of": utc_iso(current),
        "timezone": task.timezone,
        "local_date": local_date.isoformat(),
        "starting_capital": starting_capital,
    },)

    for rule in rules:
        threshold = float(rule.threshold) if rule.threshold is not None else None
        if threshold is None:
            continue
        if (
            rule.rule_type == "max_daily_realized_loss_percent"
            and starting_capital
        ):
            actual = daily_loss / starting_capital * 100
            if actual > threshold:
                findings.append(_finding(
                    rule,
                    current=actual,
                    threshold=threshold,
                    title="当日亏损已超过限制",
                    body=f"已实现亏损为 {actual:.2f}%，限制为 {threshold:.2f}%。",
                    title_en="Daily realized loss is above the limit",
                    body_en=(
                        f"Realized loss is {actual:.2f}%; the limit is "
                        f"{threshold:.2f}%."
                    ),
                    evidence=evidence_base + ({
                        "kind": "daily_realized_pnl",
                        "value": daily_realized,
                        "trade_ids": [trade.id for trade in todays_closed],
                    },),
                ))
        elif rule.rule_type == "max_total_open_risk_percent" and starting_capital:
            actual = total_exposure / starting_capital * 100
            if actual > threshold:
                findings.append(_finding(
                    rule,
                    current=actual,
                    threshold=threshold,
                    title="总计划风险已超过限制",
                    body=f"未平仓交易与活跃计划合计风险为 {actual:.2f}%，限制为 {threshold:.2f}%。",
                    title_en="Total planned risk is above the limit",
                    body_en=(
                        f"Open trades and active plans expose {actual:.2f}% of "
                        f"capital; the limit is {threshold:.2f}%."
                    ),
                    evidence=evidence_base + ({
                        "kind": "open_risk",
                        "open_trade_risk": open_risk,
                        "active_plan_risk": plan_risk,
                        "trade_ids": [trade.id for trade in open_trades],
                        "plan_ids": [plan.id for plan in plans],
                    },),
                ))
        elif rule.rule_type == "max_consecutive_losses":
            if consecutive_losses >= threshold:
                findings.append(_finding(
                    rule,
                    current=float(consecutive_losses),
                    threshold=threshold,
                    title="连续亏损达到冷静期阈值",
                    body=f"当前连续亏损 {consecutive_losses} 笔，阈值为 {int(threshold)} 笔。",
                    title_en="Consecutive losses reached the cooldown threshold",
                    body_en=(
                        f"There are {consecutive_losses} consecutive losses; "
                        f"the threshold is {int(threshold)}."
                    ),
                    evidence=evidence_base,
                ))
        elif rule.rule_type == "max_trades_per_day":
            actual = len(todays_opened)
            if actual > threshold:
                findings.append(_finding(
                    rule,
                    current=float(actual),
                    threshold=threshold,
                    title="当日交易次数已超过限制",
                    body=f"今日已记录 {actual} 笔交易，限制为 {int(threshold)} 笔。",
                    title_en="Daily trade count is above the limit",
                    body_en=(
                        f"{actual} trades are recorded today; the limit is "
                        f"{int(threshold)}."
                    ),
                    evidence=evidence_base + ({
                        "kind": "daily_trades",
                        "trade_ids": [trade.id for trade in todays_opened],
                    },),
                ))
        elif rule.rule_type == "require_stop_loss":
            for trade in open_trades:
                if trade.stop_loss is None:
                    findings.append(_finding(
                        rule,
                        current=1,
                        threshold=0,
                        title=f"{trade.symbol} 缺少止损",
                        body="未平仓记录没有止损，无法确定真实风险。",
                        title_en=f"{trade.symbol} has no stop loss",
                        body_en=(
                            "The open trade has no stop loss, so its true risk "
                            "cannot be determined."
                        ),
                        subject_type="trade",
                        subject_id=trade.id,
                        evidence=evidence_base,
                    ))

    if starting_capital is None:
        findings.append(WorkflowFinding(
            finding_type="data_quality",
            severity="info",
            fingerprint="risk:data_quality:starting_capital",
            title="尚未设置日志起始资金",
            body="部分账户级风险比例暂时无法计算。",
            title_en="Journal starting capital is not configured",
            body_en="Some account-level risk ratios cannot be calculated yet.",
            subject_type="journal_settings",
            evidence=evidence_base,
        ))
    for trade in unknown_open_risk:
        findings.append(WorkflowFinding(
            finding_type="data_quality",
            severity="warning",
            fingerprint=f"risk:data_quality:trade:{trade.id}",
            title=f"{trade.symbol} 风险数据不完整",
            body="需要入场价、止损、数量和合约规格才能计算风险。",
            title_en=f"{trade.symbol} has incomplete risk data",
            body_en=(
                "Entry price, stop loss, quantity, and instrument specifications "
                "are required to calculate risk."
            ),
            subject_type="trade",
            subject_id=trade.id,
            evidence=evidence_base,
        ))

    metrics = {
        "daily_realized_pnl": daily_realized,
        "daily_trade_count": len(todays_opened),
        "open_trade_count": len(open_trades),
        "active_plan_count": len(plans),
        "open_trade_risk": open_risk,
        "active_plan_risk": plan_risk,
        "consecutive_losses": consecutive_losses,
        "currency_code": settings.currency_code if settings else None,
    }
    summary = (
        f"发现 {len(findings)} 个风险或数据问题。"
        if findings else "未发现违反当前规则的风险。"
    )
    return WorkflowResult(
        summary=summary,
        findings=tuple(findings),
        evidence=evidence_base,
        metrics=metrics,
        as_of=utc_iso(current),
    )

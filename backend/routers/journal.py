import csv
import io
import json
import math
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api_response import success, error
from auth_dependency import get_current_user
from db import get_db
from i18n import t, get_lang
from services.billing import BillingModule, DAILY_REVIEW_UNIT_COST

router = APIRouter(prefix="/api/journal", tags=["journal"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateTradeRequest(BaseModel):
    symbol: str
    series_id: str | None = None
    direction: str
    position_status: Literal["open", "closed"] | None = None
    exchange: str | None = None
    open_price: float | None = None
    close_price: float | None = None
    quantity: float | None = None
    open_time: str | None = None
    close_time: str | None = None
    fees: float = 0
    pnl: float | None = None
    tags: list[str] | None = None
    notes: str = ""
    source: str = "manual"
    image_asset_ids: list[str] | None = None
    strategy_id: str | None = None
    plan_id: str | None = None
    target_price: float | None = None
    stop_loss: float | None = None
    setup_type: str | None = None
    emotional_state: str | None = None
    mistakes: list[str] | None = None
    confidence: int | None = Field(default=None, ge=0, le=10)
    execution_quality: int | None = Field(default=None, ge=0, le=10)


class UpdateTradeRequest(BaseModel):
    symbol: str | None = None
    series_id: str | None = None
    direction: str | None = None
    position_status: Literal["open", "closed"] | None = None
    exchange: str | None = None
    open_price: float | None = None
    close_price: float | None = None
    quantity: float | None = None
    open_time: str | None = None
    close_time: str | None = None
    fees: float | None = None
    pnl: float | None = None
    tags: list[str] | None = None
    notes: str | None = None
    source: str | None = None
    image_asset_ids: list[str] | None = None
    strategy_id: str | None = None
    plan_id: str | None = None
    target_price: float | None = None
    stop_loss: float | None = None
    setup_type: str | None = None
    emotional_state: str | None = None
    mistakes: list[str] | None = None
    confidence: int | None = Field(default=None, ge=0, le=10)
    execution_quality: int | None = Field(default=None, ge=0, le=10)


class TradePlanRequest(BaseModel):
    symbol: str
    series_id: str | None = None
    market: str = "stock"
    direction: str
    entry_price: float
    target_price: float | None = None
    stop_loss: float
    account_size: float = Field(gt=0)
    risk_percent: float = Field(gt=0, le=100)
    thesis: str = ""
    strategy_id: str | None = None


class TradingRuleRequest(BaseModel):
    name: str
    rule_type: str
    threshold: float | None = None
    weight: str = "important"


class TradingRuleUpdateRequest(BaseModel):
    active: bool


class ComplianceCheckRequest(BaseModel):
    symbol: str = ""
    direction: str = "long"
    open_price: float | None = None
    entry_price: float | None = None
    target_price: float | None = None
    stop_loss: float | None = None
    quantity: float | None = None
    account_size: float | None = None
    open_time: str | None = None
    notes: str = ""
    thesis: str = ""
    confidence: int | None = Field(default=None, ge=0, le=10)
    plan_id: str | None = None


class BatchCreateRequest(BaseModel):
    trades: list[CreateTradeRequest]


class TradeFilter(BaseModel):
    symbol: str | None = None
    direction: str | None = None
    position_status: Literal["open", "closed"] | None = None
    tag: str | None = None
    date_from: str | None = None
    date_to: str | None = None


class BatchTargetRequest(BaseModel):
    trade_ids: list[str] | None = None
    select_all_matching: bool = False
    filter: TradeFilter | None = None


class BatchTagRequest(BatchTargetRequest):
    tags: list[str]


class BatchExportRequest(BatchTargetRequest):
    format: str = "csv"


JournalCurrencyCode = Literal["CNY", "USD", "HKD", "EUR", "GBP", "JPY", "USDT"]


class JournalSettingsRequest(BaseModel):
    starting_capital: float | None = None
    currency_code: JournalCurrencyCode | None = None


class DailyReviewRequest(BaseModel):
    title: str = ""
    body: str = ""
    tags: list[str] | None = None


class DailyReviewAssistRequest(BaseModel):
    action: str
    body: str = ""
    selection: str | None = None
    date_from: str
    date_to: str
    lang: str | None = None


def _resolve_target_ids(svc, user_id: str, target: BatchTargetRequest) -> list[str] | None:
    """Resolve a BatchTargetRequest into a concrete list of trade ids.
    Returns None when the target is empty/invalid — caller maps to 400.
    """
    if target.select_all_matching:
        f = target.filter or TradeFilter()
        return svc.resolve_trade_ids_by_filter(user_id, **f.model_dump(exclude_none=True))
    if target.trade_ids:
        return target.trade_ids
    return None


class DiagnosisRequest(BaseModel):
    lang: str = "zh"
    date_from: str | None = None
    date_to: str | None = None


RULE_TYPES = {
    "max_risk_percent",
    "min_risk_reward",
    "max_trades_per_day",
    "max_daily_realized_loss_percent",
    "max_total_open_risk_percent",
    "max_consecutive_losses",
    "min_confidence",
    "require_stop_loss",
    "require_notes",
}
THRESHOLD_RULE_TYPES = {
    "max_risk_percent",
    "min_risk_reward",
    "max_trades_per_day",
    "max_daily_realized_loss_percent",
    "max_total_open_risk_percent",
    "max_consecutive_losses",
    "min_confidence",
}
RULE_WEIGHTS = {"critical", "important", "nice_to_have"}


# ---------------------------------------------------------------------------
# Service accessor
# ---------------------------------------------------------------------------


def _get_svc(session: Session = Depends(get_db)):
    from services.journal import JournalService
    return JournalService(session)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/trades")
async def create_trade(
    req: CreateTradeRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    svc=Depends(_get_svc),
):
    payload = req.model_dump(exclude_none=False)
    image_asset_ids = payload.pop("image_asset_ids")
    try:
        trade = svc.create_trade(
            user_id=user_id,
            image_asset_ids=image_asset_ids,
            **payload,
        )
    except (PermissionError, ValueError) as exc:
        if isinstance(exc, ValueError):
            return error(message=str(exc), code=400, status_code=400)
        if str(exc) == "strategy_not_found":
            return error(
                message=t("errors.strategy_not_found", get_lang(request)),
                code=400,
                status_code=400,
            )
        if str(exc) == "plan_not_found":
            return error(message="Trade plan not found", code=400, status_code=400)
        return error(message="Invalid image asset", code=400, status_code=400)
    return success(trade)


@router.get("/trades")
async def list_trades(
    symbol: str | None = None,
    direction: str | None = None,
    position_status: Literal["open", "closed"] | None = None,
    tag: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(default=20, ge=1),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(get_current_user),
    svc=Depends(_get_svc),
):
    filter_kw = dict(
        symbol=symbol, direction=direction, position_status=position_status, tag=tag,
        date_from=date_from, date_to=date_to,
    )
    total = svc.count_trades(user_id=user_id, **filter_kw)
    items = svc.list_trades(user_id=user_id, **filter_kw, limit=limit, offset=offset)
    return success({"items": items, "total": total, "limit": limit, "offset": offset})


def _sanitize_floats(obj):
    """Replace inf/-inf/nan with JSON-safe values."""
    if isinstance(obj, float):
        if math.isinf(obj) or math.isnan(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_floats(v) for v in obj]
    return obj


@router.get("/stats")
async def get_stats(
    date_from: str | None = None,
    date_to: str | None = None,
    user_id: str = Depends(get_current_user),
    svc=Depends(_get_svc),
):
    stats = svc.compute_stats(user_id=user_id, date_from=date_from, date_to=date_to)
    return success(_sanitize_floats(stats))


@router.get("/calendar")
async def get_calendar_summary(month: str, user_id: str = Depends(get_current_user), svc=Depends(_get_svc)):
    try:
      summary = svc.compute_calendar_summary(month, user_id=user_id)
    except ValueError:
      return error(message="Invalid month", code=400, status_code=400)
    return success(_sanitize_floats(summary))


@router.post("/plans")
async def create_trade_plan(
    req: TradePlanRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    svc=Depends(_get_svc),
):
    if (
        req.direction not in {"long", "short"}
        or not req.symbol.strip()
        or req.entry_price == req.stop_loss
    ):
        return error(message="Invalid trade plan", code=400, status_code=400)
    try:
        plan = svc.create_trade_plan(
            user_id=user_id,
            **{**req.model_dump(), "symbol": req.symbol.strip().upper()},
        )
    except PermissionError:
        return error(
            message=t("errors.strategy_not_found", get_lang(request)),
            code=400,
            status_code=400,
        )
    return success(plan)


@router.get("/plans")
async def list_trade_plans(
    status: str = "active",
    user_id: str = Depends(get_current_user),
    svc=Depends(_get_svc),
):
    if status not in {"active", "converted"}:
        return error(message="Invalid plan status", code=400, status_code=400)
    return success({"items": svc.list_trade_plans(user_id, status=status)})


@router.delete("/plans/{plan_id}")
async def delete_trade_plan(
    plan_id: str,
    user_id: str = Depends(get_current_user),
    svc=Depends(_get_svc),
):
    if not svc.delete_trade_plan(plan_id, user_id):
        return error(message="Trade plan not found", code=404, status_code=404)
    return success(None)


@router.post("/rules")
async def create_trading_rule(
    req: TradingRuleRequest,
    user_id: str = Depends(get_current_user),
    svc=Depends(_get_svc),
):
    if req.rule_type not in RULE_TYPES or req.weight not in RULE_WEIGHTS or not req.name.strip():
        return error(message="Invalid trading rule", code=400, status_code=400)
    if req.rule_type in THRESHOLD_RULE_TYPES and (req.threshold is None or req.threshold < 0):
        return error(message="Rule threshold is required", code=400, status_code=400)
    return success(svc.create_rule(
        user_id=user_id,
        name=req.name.strip(),
        rule_type=req.rule_type,
        threshold=req.threshold,
        weight=req.weight,
    ))


@router.get("/rules")
async def list_trading_rules(
    user_id: str = Depends(get_current_user),
    svc=Depends(_get_svc),
):
    return success({"items": svc.list_rules(user_id)})


@router.patch("/rules/{rule_id}")
async def update_trading_rule(
    rule_id: str,
    req: TradingRuleUpdateRequest,
    user_id: str = Depends(get_current_user),
    svc=Depends(_get_svc),
):
    updated = svc.update_rule(rule_id, user_id, active=int(req.active))
    if updated is None:
        return error(message="Trading rule not found", code=404, status_code=404)
    return success(updated)


@router.delete("/rules/{rule_id}")
async def delete_trading_rule(
    rule_id: str,
    user_id: str = Depends(get_current_user),
    svc=Depends(_get_svc),
):
    if not svc.delete_rule(rule_id, user_id):
        return error(message="Trading rule not found", code=404, status_code=404)
    return success(None)


@router.post("/compliance/check")
async def check_trade_compliance(
    req: ComplianceCheckRequest,
    user_id: str = Depends(get_current_user),
    svc=Depends(_get_svc),
):
    return success(svc.evaluate_compliance(user_id, req.model_dump()))


@router.get("/reviews/{review_date}")
async def get_daily_review(review_date: str, user_id: str = Depends(get_current_user), svc=Depends(_get_svc)):
    return success(svc.get_daily_review(user_id=user_id, review_date=review_date))


@router.put("/reviews/{review_date}")
async def put_daily_review(
    review_date: str,
    req: DailyReviewRequest,
    user_id: str = Depends(get_current_user),
    svc=Depends(_get_svc),
):
    review = svc.upsert_daily_review(
        user_id=user_id,
        review_date=review_date,
        **req.model_dump(exclude_none=True),
    )
    return success(review)


@router.get("/reviews/{review_date}/bundle")
async def get_daily_review_bundle(
    review_date: str,
    date_from: str,
    date_to: str,
    user_id: str = Depends(get_current_user),
    svc=Depends(_get_svc),
):
    bundle = svc.get_daily_review_bundle(
        user_id=user_id,
        review_date=review_date,
        date_from=date_from,
        date_to=date_to,
    )
    return success(_sanitize_floats(bundle))


@router.post("/reviews/{review_date}/assist")
async def assist_daily_review(
    review_date: str,
    req: DailyReviewAssistRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
    svc=Depends(_get_svc),
):
    if req.action not in {"title", "summary", "organize", "expand", "suggest"}:
        return error(message="Invalid assist action", code=400, status_code=400)
    BillingModule(session).require(
        user_id,
        "journal.ai_assist",
        units=DAILY_REVIEW_UNIT_COST,
        request_id=request.headers.get("X-Request-ID") or str(uuid4()),
    )
    result = await svc.assist_daily_review(
        user_id=user_id,
        review_date=review_date,
        action=req.action,
        body=req.body,
        selection=req.selection or "",
        date_from=req.date_from,
        date_to=req.date_to,
        lang=req.lang or "zh",
    )
    return success(result)


@router.get("/export")
async def export_trades(
    format: str = Query(default="csv"),
    symbol: str | None = None,
    direction: str | None = None,
    tag: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    user_id: str = Depends(get_current_user),
    svc=Depends(_get_svc),
):
    trades = svc.list_trades(
        user_id=user_id,
        symbol=symbol,
        direction=direction,
        tag=tag,
        date_from=date_from,
        date_to=date_to,
        limit=10000,
    )
    currency_code = svc.get_journal_settings(user_id)["currency_code"]
    trades = [{**row, "currency_code": currency_code} for row in trades]

    if format == "json":
        return success(trades)

    # CSV export
    buf = io.StringIO()
    if trades:
        fieldnames = list(trades[0].keys())
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for row in trades:
            # Serialize list values (tags) to JSON strings for CSV
            csv_row = {
                k: json.dumps(v) if isinstance(v, list) else v
                for k, v in row.items()
            }
            writer.writerow(csv_row)
    else:
        buf.write("")

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trades.csv"},
    )


@router.get("/trades/{trade_id}")
async def get_trade(trade_id: str, user_id: str = Depends(get_current_user), svc=Depends(_get_svc)):
    trade = svc.get_trade(trade_id, user_id=user_id)
    if trade is None:
        return error(message="Trade not found", code=404, status_code=404)
    return success(trade)


@router.put("/trades/{trade_id}")
async def update_trade(
    trade_id: str,
    req: UpdateTradeRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    svc=Depends(_get_svc),
):
    existing = svc.get_trade(trade_id, user_id=user_id)
    if existing is None:
        return error(message="Trade not found", code=404, status_code=404)

    # Use exclude_unset to distinguish "field not provided" from "field set to None".
    # For strategy_id: missing key = leave unchanged, value=None = clear FK,
    # value=string = set/validate. Drop None for non-strategy_id fields so we
    # don't accidentally null out columns the caller didn't intend to clear.
    set_fields = req.model_dump(exclude_unset=True)
    fields: dict = {}
    clearable_fields = {
        "series_id", "strategy_id", "plan_id", "target_price", "stop_loss", "setup_type",
        "emotional_state", "confidence", "execution_quality",
        "close_price", "close_time", "pnl",
    }
    for key, value in set_fields.items():
        if key in clearable_fields:
            fields[key] = value
        elif value is not None:
            fields[key] = value

    image_asset_ids = fields.pop("image_asset_ids", None)
    try:
        updated = svc.update_trade(
            trade_id,
            user_id=user_id,
            image_asset_ids=image_asset_ids,
            **fields,
        )
    except (PermissionError, ValueError) as exc:
        if isinstance(exc, ValueError):
            return error(message=str(exc), code=400, status_code=400)
        if str(exc) == "strategy_not_found":
            return error(
                message=t("errors.strategy_not_found", get_lang(request)),
                code=400,
                status_code=400,
            )
        if str(exc) == "plan_not_found":
            return error(message="Trade plan not found", code=400, status_code=400)
        return error(message="Invalid image asset", code=400, status_code=400)
    return success(updated)


@router.delete("/trades/{trade_id}")
async def delete_trade(trade_id: str, user_id: str = Depends(get_current_user), svc=Depends(_get_svc)):
    deleted = svc.delete_trade(trade_id, user_id=user_id)
    if not deleted:
        return error(message="Trade not found", code=404, status_code=404)
    return success(None)


@router.post("/trades/batch/delete")
async def batch_delete(
    req: BatchTargetRequest, user_id: str = Depends(get_current_user), svc=Depends(_get_svc)
):
    ids = _resolve_target_ids(svc, user_id, req)
    if ids is None:
        return error(message="No trades selected", code=400, status_code=400)
    deleted = svc.batch_delete_trades(ids, user_id=user_id)
    return success({"deleted": deleted})


@router.post("/trades/batch/tag")
async def batch_tag(
    req: BatchTagRequest, user_id: str = Depends(get_current_user), svc=Depends(_get_svc)
):
    if not req.tags:
        return error(message="No tags provided", code=400, status_code=400)
    ids = _resolve_target_ids(svc, user_id, req)
    if ids is None:
        return error(message="No trades selected", code=400, status_code=400)
    updated = svc.batch_add_tags(ids, user_id=user_id, tags=req.tags)
    return success({"updated": updated})


@router.post("/trades/export")
async def export_trades_selected(
    req: BatchExportRequest, user_id: str = Depends(get_current_user), svc=Depends(_get_svc)
):
    ids = _resolve_target_ids(svc, user_id, req)
    if ids is None:
        return error(message="No trades selected", code=400, status_code=400)

    # Fetch full rows for the resolved ids in a single query
    trades = svc.list_trades_by_ids(ids, user_id=user_id)
    currency_code = svc.get_journal_settings(user_id)["currency_code"]
    trades = [{**row, "currency_code": currency_code} for row in trades]

    if req.format == "json":
        return success(trades)

    buf = io.StringIO()
    if trades:
        fieldnames = list(trades[0].keys())
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for row in trades:
            csv_row = {
                k: json.dumps(v) if isinstance(v, list) else v
                for k, v in row.items()
            }
            writer.writerow(csv_row)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trades.csv"},
    )


@router.post("/trades/batch")
async def batch_create_trades(req: BatchCreateRequest, user_id: str = Depends(get_current_user), svc=Depends(_get_svc)):
    if any(t.image_asset_ids is not None for t in req.trades):
        return error(
            message="Images are not supported in batch create",
            code=400,
            status_code=400,
        )
    trades_data = [t.model_dump(exclude_none=False) for t in req.trades]
    created = svc.batch_create_trades(trades_data, user_id=user_id)
    return success(created)


@router.post("/diagnosis")
async def create_diagnosis_job(req: DiagnosisRequest, user_id: str = Depends(get_current_user), svc=Depends(_get_svc)):
    job = svc.create_diagnosis_job(user_id=user_id, lang=req.lang, date_from=req.date_from, date_to=req.date_to)
    return success({"job_id": job.job_id, "status": job.status, "created_at": job.created_at})


@router.get("/diagnosis/{job_id}")
async def get_diagnosis_job(job_id: str, user_id: str = Depends(get_current_user)):
    from services.journal import JournalService
    job = JournalService.get_diagnosis_job(job_id)
    if job is None:
        return error(message="Job not found", code=404, status_code=404)
    result = {
        "job_id": job.job_id,
        "status": job.status,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "result": job.result,
        "error": job.error,
    }
    return success(result)


@router.get("/settings")
async def get_journal_settings(user_id: str = Depends(get_current_user), svc=Depends(_get_svc)):
    return success(svc.get_journal_settings(user_id=user_id))


@router.patch("/settings")
@router.put("/settings")
async def put_journal_settings(
    req: JournalSettingsRequest,
    user_id: str = Depends(get_current_user),
    svc=Depends(_get_svc),
):
    updates = req.model_dump(exclude_unset=True)
    starting_capital = updates.get("starting_capital")
    if starting_capital is not None and starting_capital < 0:
        return error(message="starting_capital must be non-negative", code=400, status_code=400)
    return success(svc.update_journal_settings(user_id=user_id, updates=updates))

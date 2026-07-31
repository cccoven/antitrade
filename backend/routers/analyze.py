from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from api_response import success, ApiResponse
from auth_dependency import get_current_user
from db import get_db
from services.billing import ANALYSIS_UNIT_COST, BillingModule
from services.analyzer import (
    create_analysis_job,
    get_analysis_job,
    get_latest_analysis,
)

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    symbol: str
    exchange: str
    interval: str
    lang: str = "zh"
    force_refresh: bool = False


class AnalyzeResponse(BaseModel):
    symbol: str
    exchange: str
    interval: str
    analysis: str
    analyzed_at: str


class AnalyzeJobResponse(BaseModel):
    job_id: str
    symbol: str
    exchange: str
    interval: str
    status: str
    created_at: str
    updated_at: str
    result: AnalyzeResponse | None = None
    error: str | None = None


class LatestAnalyzeResponse(BaseModel):
    symbol: str
    exchange: str
    interval: str
    analysis: str
    analyzed_at: str


def build_job_response(job) -> AnalyzeJobResponse:
    result = None
    if job.analysis is not None and job.analyzed_at is not None:
        result = AnalyzeResponse(
            symbol=job.symbol,
            exchange=job.exchange,
            interval=job.interval,
            analysis=job.analysis,
            analyzed_at=job.analyzed_at,
        )

    return AnalyzeJobResponse(
        job_id=job.job_id,
        symbol=job.symbol,
        exchange=job.exchange,
        interval=job.interval,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        result=result,
        error=job.error,
    )


@router.post("/jobs", response_model=ApiResponse[AnalyzeJobResponse])
async def create_job(
    req: AnalyzeRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    BillingModule(session).require(
        user_id,
        "analysis.run",
        units=ANALYSIS_UNIT_COST,
        request_id=request.headers.get("X-Request-ID") or str(uuid4()),
    )
    job = create_analysis_job(
        symbol=req.symbol,
        exchange=req.exchange,
        interval=req.interval,
        lang=req.lang,
        force_refresh=req.force_refresh,
    )
    return success(build_job_response(job))


@router.get("/jobs/{job_id}", response_model=ApiResponse[AnalyzeJobResponse | None])
async def get_job(job_id: str):
    job = get_analysis_job(job_id)
    return success(build_job_response(job)) if job else success(None)


@router.get("/latest", response_model=ApiResponse[LatestAnalyzeResponse | None])
async def get_latest(symbol: str, exchange: str, interval: str):
    latest = get_latest_analysis(symbol=symbol, exchange=exchange, interval=interval)
    if latest is None:
        return success(None)

    return success(
        LatestAnalyzeResponse(
            symbol=symbol,
            exchange=exchange,
            interval=interval,
            analysis=latest.analysis,
            analyzed_at=latest.analyzed_at,
        )
    )

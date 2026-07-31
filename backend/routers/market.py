from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from api_response import success
from db import get_db
from i18n import get_lang
from services.market_hours import get_market_hours
from services.market_briefing import get_daily_market_briefing
from services.market_overview_snapshot import (
    get_market_overview_snapshot,
    refresh_market_overview_snapshot,
)
from services.market_research import get_economic_calendar
from services.market_data_runtime import get_market_data_gateway
from services.market_gateway import InstrumentSearch


router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/instruments")
def search_market_instruments(
    q: str = Query(min_length=1, max_length=64),
    asset_class: str | None = None,
    venue: str | None = None,
    provider: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
):
    matches = get_market_data_gateway().search_instruments(
        InstrumentSearch(
            text=q,
            asset_class=asset_class,
            venue=venue,
            provider=provider,
            limit=limit,
        ),
    )
    return success({
        "items": [
            {
                "series_id": match.series_id,
                "symbol": match.display_symbol,
                "name": match.display_name,
                "asset_class": match.asset_class,
                "venue": match.venue,
                "series_kind": match.series_kind,
            }
            for match in matches
            if match.series_id is not None
        ],
    })


@router.get("/overview")
def market_overview(force_refresh: bool = False):
    if force_refresh:
        return success(refresh_market_overview_snapshot(force_refresh=True))
    return success(get_market_overview_snapshot())


@router.get("/economic-calendar")
def economic_calendar():
    return success(get_economic_calendar())


@router.get("/daily-briefing")
async def daily_market_briefing(
    request: Request,
    lang: str | None = None,
    force_refresh: bool = False,
    session: Session = Depends(get_db),
):
    resolved_lang = lang or get_lang(request)
    return success(await get_daily_market_briefing(
        session=session,
        lang=resolved_lang,
        force_refresh=force_refresh,
    ))


@router.get("/hours")
def market_hours(timezone_name: str = Query("Asia/Shanghai", alias="timezone")):
    try:
        return success(get_market_hours(timezone_name))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid timezone") from exc

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api_response import success, error
from auth_dependency import get_current_user
from db import get_db
from services.market_data_runtime import get_market_data_gateway
from services.replay import ReplayProblem, ReplayService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/replay", tags=["replay"])


def _get_journal_svc(session: Session = Depends(get_db)):
    from services.journal import JournalService
    return JournalService(session)


def _get_replay_svc():
    return ReplayService(get_market_data_gateway())


@router.get("/{trade_id}")
def get_replay(
    trade_id: str,
    interval: str = Query(default="auto"),
    window: str = Query(default="standard"),
    user_id: str = Depends(get_current_user),
    svc=Depends(_get_journal_svc),
    replay_svc: ReplayService = Depends(_get_replay_svc),
):
    trade = svc.get_trade(trade_id, user_id=user_id)
    if trade is None:
        return error(
            message="replay_unavailable",
            code=404,
            status_code=404,
            data={
                "problem": "trade_not_found",
                "retryable": False,
                "suggested_intervals": [],
            },
        )

    try:
        bundle = replay_svc.prepare(trade, interval=interval, window=window)
    except ReplayProblem as exc:
        return error(
            message="replay_unavailable",
            code=exc.status_code,
            status_code=exc.status_code,
            data=exc.to_dict(),
        )
    except ValueError as exc:
        logger.info("Invalid replay request", extra={"reason": str(exc)})
        return error(
            message="replay_invalid_request",
            code=400,
            status_code=400,
        )
    except Exception as exc:  # pragma: no cover — defensive
        logger.exception("Replay bundle assembly failed", exc_info=exc)
        return error(message="replay_failed", code=500, status_code=500)

    return success(bundle)

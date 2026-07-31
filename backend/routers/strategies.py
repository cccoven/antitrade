from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api_response import success
from auth_dependency import get_current_user
from db import get_db
from services.strategies import StrategyService

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


class CreateStrategyRequest(BaseModel):
    title: str | None = None
    body: str | None = None
    tags: list[str] | None = None


class PatchStrategyRequest(BaseModel):
    title: str | None = None
    body: str | None = None
    tags: list[str] | None = None


@router.get("")
async def list_strategies(
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return success(StrategyService(session).list_strategies(user_id=user_id))


@router.get("/options")
async def list_options(
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return success(StrategyService(session).list_strategy_options(user_id=user_id))


@router.post("")
async def create_strategy(
    req: CreateStrategyRequest,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    payload = {k: v for k, v in req.model_dump().items() if v is not None}
    return success(StrategyService(session).create_strategy(user_id=user_id, **payload))


@router.get("/{strategy_id}")
async def get_strategy(
    strategy_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    s = StrategyService(session).get_strategy(user_id=user_id, strategy_id=strategy_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return success(s)


@router.patch("/{strategy_id}")
async def patch_strategy(
    strategy_id: str,
    req: PatchStrategyRequest,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    payload = {k: v for k, v in req.model_dump().items() if v is not None}
    s = StrategyService(session).patch_strategy(user_id=user_id, strategy_id=strategy_id, **payload)
    if s is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return success(s)


@router.delete("/{strategy_id}")
async def delete_strategy(
    strategy_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    ok = StrategyService(session).delete_strategy(user_id=user_id, strategy_id=strategy_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return success({"ok": True})

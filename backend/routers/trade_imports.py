"""Reviewable trade-import endpoints."""

from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api_response import success
from auth_dependency import get_current_user
from db import get_db
from services.billing import BillingModule, RECOGNITION_UNIT_COST
from services.trade_imports import TradeImportModule
from services.uploads import UploadService

router = APIRouter(prefix="/api/trade-imports", tags=["trade-imports"])


class ReviseImportRequest(BaseModel):
    mapping: dict[str, str]


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.post("")
async def prepare_import(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    if (file.content_type or "").startswith("image/"):
        BillingModule(session).require(
            user_id,
            "recognition.parse",
            units=RECOGNITION_UNIT_COST,
            request_id=request.headers.get("X-Request-ID") or str(uuid4()),
        )
    try:
        asset = await UploadService(session).create_asset(file, user_id)
        draft = await TradeImportModule(session).prepare_import(
            user_id, asset["id"],
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return success(draft)


@router.get("/{batch_id}")
def get_import(
    batch_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    row = TradeImportModule(session).get_import(user_id, batch_id)
    if row is None:
        raise HTTPException(status_code=404, detail="trade_import_not_found")
    return success(row)


@router.patch("/{batch_id}")
def revise_import(
    batch_id: str,
    req: ReviseImportRequest,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        row = TradeImportModule(session).revise_import(
            user_id, batch_id, req.mapping,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="trade_import_not_found")
    return success(row)


@router.post("/{batch_id}/commit")
def commit_import(
    batch_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        row = TradeImportModule(session).commit_import(user_id, batch_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="trade_import_not_found")
    return success(row)


@router.post("/{batch_id}/cancel")
def cancel_import(
    batch_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        row = TradeImportModule(session).cancel_import(user_id, batch_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="trade_import_not_found")
    return success(row)

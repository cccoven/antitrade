"""Portfolio router — /api/portfolio/*"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api_response import error, success
from auth_dependency import get_current_user
from db import get_db
from services.portfolio import (
    CategoryService,
    CsvService,
    EntryService,
    PortfoliosService,
    SummaryService,
)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

MAX_IMPORT_BYTES = 5 * 1024 * 1024  # 5 MB


# ---------- Portfolios ----------

class CreatePortfolioRequest(BaseModel):
    name: str = Field(..., min_length=1)
    currency: str = Field(..., min_length=1)


class UpdatePortfolioRequest(BaseModel):
    name: str | None = None
    currency: str | None = None


@router.post("/portfolios")
async def create_portfolio(
    req: CreatePortfolioRequest,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        return success(PortfoliosService(session).create(user_id=user_id, name=req.name, currency=req.currency))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/portfolios")
async def list_portfolios(
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return success({"items": PortfoliosService(session).list(user_id=user_id)})


@router.patch("/portfolios/{portfolio_id}")
async def update_portfolio(
    portfolio_id: str,
    req: UpdatePortfolioRequest,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    result = PortfoliosService(session).update(portfolio_id, user_id=user_id, **req.model_dump(exclude_unset=True))
    if result is None:
        raise HTTPException(status_code=404, detail="portfolio not found")
    return success(result)


@router.delete("/portfolios/{portfolio_id}")
async def delete_portfolio(
    portfolio_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    deleted_entries = PortfoliosService(session).delete(portfolio_id, user_id=user_id)
    if deleted_entries is None:
        raise HTTPException(status_code=404, detail="portfolio not found")
    return success({"deleted": True, "deleted_entries": deleted_entries})


# ---------- Entries ----------

class CreateEntryRequest(BaseModel):
    name: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    amount: float = Field(..., ge=0)
    platform: str | None = None
    notes: str = ""


class UpdateEntryRequest(BaseModel):
    name: str | None = None
    category: str | None = None
    amount: float | None = Field(default=None, ge=0)
    platform: str | None = None
    notes: str | None = None


class BatchDeleteRequest(BaseModel):
    ids: list[str]


@router.post("/portfolios/{portfolio_id}/entries")
async def create_entry(
    portfolio_id: str,
    req: CreateEntryRequest,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        return success(
            EntryService(session).create(
                portfolio_id=portfolio_id, user_id=user_id,
                name=req.name, category=req.category, amount=req.amount,
                platform=req.platform, notes=req.notes,
            )
        )
    except PermissionError:
        raise HTTPException(status_code=404, detail="portfolio not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/portfolios/{portfolio_id}/entries")
async def list_entries(
    portfolio_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
    category: str | None = None,
    platform: str | None = None,
    search: str | None = None,
    sort: str = "updated_at_desc",
):
    try:
        items = EntryService(session).list(
            portfolio_id=portfolio_id, user_id=user_id,
            category=category, platform=platform, search=search, sort=sort,
        )
    except PermissionError:
        raise HTTPException(status_code=404, detail="portfolio not found")
    return success({"items": items})


@router.patch("/entries/{entry_id}")
async def update_entry(
    entry_id: str,
    req: UpdateEntryRequest,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        entry = EntryService(session).update(entry_id, user_id=user_id, **req.model_dump(exclude_unset=True))
    except PermissionError:
        raise HTTPException(status_code=404, detail="entry not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if entry is None:
        raise HTTPException(status_code=404, detail="entry not found")
    return success(entry)


@router.delete("/entries/{entry_id}")
async def delete_entry(
    entry_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        ok = EntryService(session).delete(entry_id, user_id=user_id)
    except PermissionError:
        raise HTTPException(status_code=404, detail="entry not found")
    if not ok:
        raise HTTPException(status_code=404, detail="entry not found")
    return success({"deleted": True})


@router.post("/entries/batch/delete")
async def batch_delete(
    req: BatchDeleteRequest,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return success({"deleted": EntryService(session).batch_delete(req.ids, user_id=user_id)})


# ---------- Categories ----------

class CreateCategoryRequest(BaseModel):
    name: str = Field(..., min_length=1)
    kind: str = Field(..., pattern="^(asset|liability)$")


@router.get("/categories")
async def list_categories(
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return success({"items": CategoryService(session).list(user_id=user_id)})


@router.post("/categories")
async def create_category(
    req: CreateCategoryRequest,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        return success(CategoryService(session).create(user_id=user_id, name=req.name, kind=req.kind))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/categories/{cat_id}")
async def delete_category(
    cat_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    ok, reason, entry_count = CategoryService(session).delete(cat_id, user_id=user_id)
    if ok:
        return success({"deleted": True})
    if reason == "not_found":
        raise HTTPException(status_code=404, detail="category not found")
    if reason == "preset_readonly":
        raise HTTPException(status_code=400, detail="preset categories cannot be deleted")
    if reason == "has_entries":
        return error(
            message="category still has entries", code=1, status_code=400,
            data={"entry_count": entry_count},
        )
    raise HTTPException(status_code=500, detail="unknown error")


# ---------- CSV import/export ----------

@router.get("/portfolios/{portfolio_id}/entries/export")
async def export_entries(
    portfolio_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    text = CsvService(session).export_csv(portfolio_id=portfolio_id, user_id=user_id)
    if text is None:
        raise HTTPException(status_code=404, detail="portfolio not found")

    def _iter():
        yield text

    return StreamingResponse(
        _iter(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=portfolio-{portfolio_id}.csv"},
    )


@router.post("/portfolios/{portfolio_id}/entries/import")
async def import_entries(
    portfolio_id: str,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    raw = await file.read()
    if len(raw) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="file too large (max 5 MB)")
    try:
        csv_text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="file must be UTF-8 encoded CSV")
    try:
        return success(CsvService(session).import_csv(portfolio_id=portfolio_id, user_id=user_id, csv_text=csv_text))
    except PermissionError:
        raise HTTPException(status_code=404, detail="portfolio not found")


# ---------- Summary ----------

@router.get("/portfolios/{portfolio_id}/summary")
async def get_portfolio_summary(
    portfolio_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    result = SummaryService(session).build(portfolio_id, user_id=user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="portfolio not found")
    return success(result)

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api_response import success
from auth_dependency import get_current_user
from db import get_db
from i18n import get_lang
from services.feed import FeedService

router = APIRouter(prefix="/api/feed", tags=["feed"])


class BookmarkRequest(BaseModel):
    feed_item_id: str


@router.get("/items")
async def list_items(
    page: int = 1, page_size: int = 20,
    category: str | None = None, source: str | None = None,
    lang: str | None = None, q: str | None = None, symbol: str | None = None,
    session: Session = Depends(get_db),
):
    return success(FeedService(session).list_items(
        page=page, page_size=page_size, category=category, source=source,
        lang=lang, q=q, symbol=symbol))


@router.get("/items/{item_id}")
async def get_item(item_id: str, session: Session = Depends(get_db)):
    item = FeedService(session).get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Feed item not found")
    return success(item)


@router.get("/briefing/latest")
async def latest_briefing(request: Request, lang: str | None = None,
                          session: Session = Depends(get_db)):
    resolved = lang or get_lang(request)
    return success(FeedService(session).get_latest_briefing(resolved))


@router.get("/bookmarks")
async def list_bookmarks(
    user_id: str = Depends(get_current_user), session: Session = Depends(get_db),
):
    return success(FeedService(session).list_bookmarks(user_id))


@router.get("/bookmarks/items")
async def list_bookmark_items(
    page: int = 1, page_size: int = 20,
    user_id: str = Depends(get_current_user), session: Session = Depends(get_db),
):
    return success(FeedService(session).list_bookmarked_items(
        user_id, page=page, page_size=page_size))


@router.post("/bookmarks")
async def add_bookmark(
    req: BookmarkRequest,
    user_id: str = Depends(get_current_user), session: Session = Depends(get_db),
):
    result = FeedService(session).add_bookmark(user_id, req.feed_item_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Feed item not found")
    return success(result)


@router.delete("/bookmarks/{bookmark_id}")
async def remove_bookmark(
    bookmark_id: str,
    user_id: str = Depends(get_current_user), session: Session = Depends(get_db),
):
    ok = FeedService(session).remove_bookmark(user_id, bookmark_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    return success({"ok": True})

"""Chat router — conversation-based AI assistant with SSE streaming."""

import asyncio
import json
import logging
from typing import AsyncIterator, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from api_response import error, success
from auth_dependency import get_current_user
from db import get_db
from i18n import get_lang, t
from services.chat import ChatService, MAX_CHAT_ATTACHMENTS
from services.billing import (
    BillingModule,
    CHAT_UNIT_COST,
    PROMPT_OPTIMIZE_UNIT_COST,
    VISION_UNIT_COST,
    WEB_SEARCH_UNIT_COST,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])
_SSE_HEARTBEAT_SECONDS = 15


def _billing_request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID") or str(uuid4())


def _require_chat_access(
    session: Session,
    user_id: str,
    req: "SendMessageRequest",
    request: Request,
) -> None:
    billing = BillingModule(session)
    if req.mode == "research":
        billing.require(user_id, "assistant.research")
    if req.web_search:
        billing.require(user_id, "assistant.web_search")
    if req.attachment_ids:
        billing.require(user_id, "assistant.vision")
    units = CHAT_UNIT_COST[req.mode]
    if req.web_search:
        units += WEB_SEARCH_UNIT_COST
    if req.attachment_ids:
        units += VISION_UNIT_COST
    billing.require(
        user_id,
        "assistant.basic",
        units=units,
        request_id=_billing_request_id(request),
    )


def _encode_sse(chunk: str | dict) -> str:
    if isinstance(chunk, dict):
        payload = json.dumps(chunk, ensure_ascii=False)
    else:
        payload = json.dumps({"type": "delta", "content": chunk}, ensure_ascii=False)
    return f"data: {payload}\n\n"


async def _sse_events(
    source: AsyncIterator[str | dict], lang: str,
) -> AsyncIterator[str]:
    iterator = source.__aiter__()
    pending: asyncio.Task | None = None
    try:
        while True:
            if pending is None:
                pending = asyncio.create_task(iterator.__anext__())
            done, _ = await asyncio.wait({pending}, timeout=_SSE_HEARTBEAT_SECONDS)
            if not done:
                yield ": ping\n\n"
                continue
            try:
                chunk = pending.result()
            except StopAsyncIteration:
                break
            pending = None
            yield _encode_sse(chunk)
        yield _encode_sse({"type": "done"})
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("SSE stream error", exc_info=exc)
        yield _encode_sse({"type": "error", "content": t("chat.error", lang)})
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
        await iterator.aclose()


def _stream_response(source: AsyncIterator[str | dict], lang: str) -> StreamingResponse:
    return StreamingResponse(
        _sse_events(source, lang),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


class SendMessageRequest(BaseModel):
    content: str = Field(default="", max_length=12000)
    attachment_ids: list[str] | None = Field(
        default=None, max_length=MAX_CHAT_ATTACHMENTS,
    )
    mode: Literal["quick", "standard", "research"] = "standard"
    web_search: bool = False

    @model_validator(mode="after")
    def require_content_or_attachment(self):
        if not self.content.strip() and not self.attachment_ids:
            raise ValueError("message must include content or an attachment")
        if self.attachment_ids and len(self.attachment_ids) != len(set(self.attachment_ids)):
            raise ValueError("attachment ids must be unique")
        return self


class OptimizePromptRequest(BaseModel):
    content: str = Field(min_length=3, max_length=12000)


class ResumeDecision(BaseModel):
    call_id: str = Field(min_length=1, max_length=200)
    decision: Literal["approve", "reject"]


class ResumeRequest(BaseModel):
    decisions: list[ResumeDecision] = Field(min_length=1, max_length=20)


class UpdateConversationRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    pinned: bool | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("title must not be blank")
        return normalized


class ReorderConversationsRequest(BaseModel):
    conversation_ids: list[str] = Field(min_length=1)


@router.get("/capabilities")
async def get_capabilities(
    _user_id: str = Depends(get_current_user),
):
    from config import FRED_API_KEY
    from services.assistant_commands import list_assistant_commands
    from services.agent import is_vision_available
    from services.web_search import is_web_search_available

    available = is_web_search_available()
    return success({
        "web_search": {
            "available": available,
            "provider": "tavily" if available else None,
        },
        "vision": {
            "available": is_vision_available(),
            "max_images": MAX_CHAT_ATTACHMENTS,
            "mime_types": ["image/png", "image/jpeg", "image/webp"],
        },
        "commands": list_assistant_commands(),
        "market_data": {
            "stock": {
                "configured": True,
                "provider": "market_gateway",
            },
            "forex": {
                "configured": True,
                "provider": "market_gateway",
            },
            "crypto": {
                "configured": True,
                "provider": "market_gateway",
            },
            "macro": {
                "configured": bool(FRED_API_KEY),
                "provider": "fred" if FRED_API_KEY else None,
            },
            "futures": {"configured": True, "provider": "market_gateway"},
        },
    })


@router.post("/optimize")
async def optimize_user_prompt(
    req: OptimizePromptRequest,
    request: Request,
    _user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    from services.prompt_optimizer import optimize_prompt

    lang = get_lang(request)
    BillingModule(session).require(
        _user_id,
        "assistant.optimize",
        units=PROMPT_OPTIMIZE_UNIT_COST,
        request_id=_billing_request_id(request),
    )
    try:
        optimized = await optimize_prompt(req.content, lang)
    except Exception as exc:
        logger.exception("Prompt optimization failed", exc_info=exc)
        return error(t("chat.optimize.error", lang), status_code=503)
    return success({"optimized": optimized})


@router.get("/conversations")
async def list_conversations(
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return success(ChatService(session).list_conversations(user_id))


@router.post("/conversations")
async def create_conversation(
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return success(ChatService(session).create_conversation(user_id))


@router.put("/conversations/order")
async def reorder_conversations(
    req: ReorderConversationsRequest,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    reordered = ChatService(session).reorder_conversations(
        user_id,
        req.conversation_ids,
    )
    if reordered is None:
        raise HTTPException(status_code=409, detail="Conversation list changed")
    return success(reordered)


@router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    req: UpdateConversationRequest,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    updated = ChatService(session).update_conversation(
        conversation_id,
        user_id,
        title=req.title,
        pinned=req.pinned,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return success(updated)


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    svc = ChatService(session)
    page = svc.get_message_page(
        conversation_id, user_id, limit=limit, offset=offset,
    )
    if page is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return success(page)


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    if not ChatService(session).delete_conversation(conversation_id, user_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return success({"deleted": True})


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    req: SendMessageRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    svc = ChatService(session)
    if svc.get_conversation(conversation_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    lang = get_lang(request)
    attachment_ids = req.attachment_ids or []
    if attachment_ids:
        from services.agent import is_vision_available

        if not is_vision_available():
            raise HTTPException(status_code=400, detail=t("chat.vision.unavailable", lang))
        try:
            svc.validate_attachment_ids(user_id, attachment_ids)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=t("chat.vision.invalid_attachments", lang),
            )
    content = req.content.strip() or t("chat.vision.default_prompt", lang)
    _require_chat_access(session, user_id, req, request)

    return _stream_response(
        svc.send_message(
            conversation_id, user_id, content, lang,
            mode=req.mode, web_search=req.web_search,
            attachment_ids=attachment_ids,
        ),
        lang,
    )


@router.put("/conversations/{conversation_id}/messages/last")
async def replace_last_message(
    conversation_id: str,
    req: SendMessageRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    svc = ChatService(session)
    if svc.get_conversation(conversation_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    lang = get_lang(request)
    if req.attachment_ids:
        from services.agent import is_vision_available

        if not is_vision_available():
            raise HTTPException(status_code=400, detail=t("chat.vision.unavailable", lang))
        try:
            svc.validate_attachment_ids(user_id, req.attachment_ids)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=t("chat.vision.invalid_attachments", lang),
            )
    content = req.content.strip() or t("chat.vision.default_prompt", lang)
    _require_chat_access(session, user_id, req, request)
    if not svc.replace_last_user_turn(
        conversation_id, user_id, content, req.attachment_ids,
    ):
        raise HTTPException(status_code=409, detail="No user message to replace")

    return _stream_response(
        svc.regenerate_last_answer(
            conversation_id, user_id, lang,
            mode=req.mode, web_search=req.web_search,
        ),
        lang,
    )


@router.post("/conversations/{conversation_id}/resume")
async def resume_run(
    conversation_id: str,
    req: ResumeRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    svc = ChatService(session)
    if svc.get_conversation(conversation_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    lang = get_lang(request)
    decisions = [d.model_dump() for d in req.decisions]

    return _stream_response(
        svc.resume_run(conversation_id, user_id, decisions, lang),
        lang,
    )

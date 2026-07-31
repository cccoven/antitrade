"""User notification settings and provider integration endpoints."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api_response import success
from auth_dependency import get_current_user
from config import TELEGRAM_WEBHOOK_SECRET
from db import get_db
from i18n import get_lang, t
from services.discord_channel import DiscordBindingService
from services.notification_channels import ChannelError, ChannelMessage, get_channel_adapters
from services.notifications import NotificationService
from services.telegram_channel import TelegramBindingService

router = APIRouter(tags=["notifications"])


class TelegramConnectRequest(BaseModel):
    locale: str = Field(default="zh", pattern="^(zh|en)$")


class DiscordConnectRequest(BaseModel):
    webhook_url: str = Field(min_length=1, max_length=500)
    locale: str = Field(default="zh", pattern="^(zh|en)$")


class SubscriptionRequest(BaseModel):
    channel_id: str
    event_type: str = Field(pattern=r"^[a-z0-9_.-]{1,120}$")
    subject_type: str | None = Field(default=None, max_length=80)
    subject_id: str | None = Field(default=None, max_length=160)
    enabled: bool = True
    locale: str = Field(default="zh", pattern="^(zh|en)$")


def _channel_http_error(exc: ChannelError, lang: str) -> HTTPException:
    status = 404 if exc.code == "channel_not_found" else 503 if exc.code == "channel_unavailable" else 400
    return HTTPException(status_code=status, detail=t(f"notifications.error.{exc.code}", lang))


@router.get("/api/notifications/channels")
def list_channels(
    request: Request,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return success(NotificationService(session).list_channels(user_id, get_lang(request)))


@router.post("/api/notifications/channels/telegram/connect")
def connect_telegram(
    req: TelegramConnectRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        return success(TelegramBindingService(session).connect(user_id, req.locale))
    except ChannelError as exc:
        raise _channel_http_error(exc, get_lang(request)) from exc


@router.post("/api/notifications/channels/discord/connect")
def connect_discord(
    req: DiscordConnectRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        return success(DiscordBindingService(session).connect(user_id, req.webhook_url, req.locale))
    except ChannelError as exc:
        raise _channel_http_error(exc, get_lang(request)) from exc


@router.post("/api/notifications/channels/{channel_id}/test")
def test_channel(
    channel_id: str,
    request: Request,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    lang = get_lang(request)
    notifications = NotificationService(session)
    channel = notifications.get_channel(user_id, channel_id)
    if channel is None:
        raise _channel_http_error(ChannelError("channel_not_found"), lang)
    adapter = get_channel_adapters().get(channel.channel_type)
    if adapter is None:
        raise _channel_http_error(ChannelError("channel_unavailable"), lang)
    channel_name = channel.channel_type.title()
    message = (
        ChannelMessage("AntiTrade test notification", f"{channel_name} notifications are ready.")
        if lang == "en"
        else ChannelMessage("AntiTrade 测试通知", f"{channel_name} 通知已准备就绪。")
    )
    try:
        result = adapter.send(channel, message)
    except ChannelError as exc:
        raise _channel_http_error(exc, lang) from exc
    return success({"ok": True, "provider_message_id": result.provider_message_id})


@router.delete("/api/notifications/channels/{channel_id}")
def remove_channel(
    channel_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    if not NotificationService(session).remove_channel(user_id, channel_id):
        raise HTTPException(status_code=404, detail="Notification channel not found")
    return success({"ok": True})


@router.get("/api/notifications/subscriptions")
def list_subscriptions(
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return success(NotificationService(session).list_subscriptions(user_id))


@router.put("/api/notifications/subscriptions")
def upsert_subscription(
    req: SubscriptionRequest,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    row = NotificationService(session).upsert_subscription(
        user_id=user_id,
        channel_id=req.channel_id,
        event_type=req.event_type,
        subject_type=req.subject_type,
        subject_id=req.subject_id,
        enabled=req.enabled,
        locale=req.locale,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Notification channel not found")
    return success(row)


@router.delete("/api/notifications/subscriptions/{subscription_id}")
def remove_subscription(
    subscription_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    if not NotificationService(session).remove_subscription(user_id, subscription_id):
        raise HTTPException(status_code=404, detail="Notification subscription not found")
    return success({"ok": True})


@router.get("/api/notifications/deliveries")
def list_deliveries(
    limit: int = 20,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return success(NotificationService(session).list_deliveries(user_id, limit))


@router.get("/api/notifications/inbox")
def list_inbox(
    request: Request,
    unread_only: bool = False,
    cursor: str | None = None,
    limit: int = 20,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        result = NotificationService(session).list_inbox(
            user_id,
            locale=get_lang(request),
            unread_only=unread_only,
            cursor=cursor,
            limit=limit,
        )
    except ValueError as exc:
        if str(exc) == "notification_inbox_cursor_not_found":
            raise HTTPException(status_code=404, detail="Notification cursor not found") from exc
        raise
    return success(result)


@router.get("/api/notifications/inbox/unread-count")
def inbox_unread_count(
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return success({"count": NotificationService(session).inbox_unread_count(user_id)})


@router.post("/api/notifications/inbox/{delivery_id}/read")
def mark_inbox_read(
    delivery_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    if not NotificationService(session).mark_inbox_read(user_id, delivery_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    return success({"ok": True})


@router.post("/api/notifications/inbox/read-all")
def mark_all_inbox_read(
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    updated = NotificationService(session).mark_all_inbox_read(user_id)
    return success({"updated": updated})


@router.delete("/api/notifications/inbox/{delivery_id}")
def remove_inbox_message(
    delivery_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    if not NotificationService(session).remove_inbox_message(user_id, delivery_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    return success({"ok": True})


@router.post("/api/integrations/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    session: Session = Depends(get_db),
):
    if not TELEGRAM_WEBHOOK_SECRET or not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        x_telegram_bot_api_secret_token, TELEGRAM_WEBHOOK_SECRET
    ):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    payload = await request.json()
    return success(TelegramBindingService(session).handle_start(payload))

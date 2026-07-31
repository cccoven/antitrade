"""Telegram notification channel and account binding."""

from __future__ import annotations

import hashlib
import html
import logging
import secrets
from datetime import timedelta
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import (
    APP_PUBLIC_URL,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_BOT_USERNAME,
    TELEGRAM_WEBHOOK_BASE_URL,
    TELEGRAM_WEBHOOK_SECRET,
)
from models import NotificationChannel
from services.notification_channels import ChannelError, ChannelMessage, SendResult
from services.notifications import NotificationService, parse_utc, utc_now

logger = logging.getLogger(__name__)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def configure_telegram_webhook() -> bool:
    """Register the production webhook when all required settings are present."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_WEBHOOK_BASE_URL or not TELEGRAM_WEBHOOK_SECRET:
        return False
    api_url = f"https://api.telegram.org/bot{quote(TELEGRAM_BOT_TOKEN, safe=':')}/setWebhook"
    webhook_url = f"{TELEGRAM_WEBHOOK_BASE_URL}/api/integrations/telegram/webhook"
    try:
        response = httpx.post(
            api_url,
            json={
                "url": webhook_url,
                "secret_token": TELEGRAM_WEBHOOK_SECRET,
                "allowed_updates": ["message"],
            },
            timeout=10.0,
        )
        configured = response.is_success and bool(response.json().get("ok"))
    except (httpx.RequestError, ValueError):
        configured = False
    if configured:
        logger.info("telegram webhook configured")
    else:
        logger.warning("telegram webhook configuration failed")
    return configured


class TelegramChannelAdapter:
    def __init__(self, token: str | None = None, public_url: str | None = None):
        self.token = TELEGRAM_BOT_TOKEN if token is None else token
        self.public_url = APP_PUBLIC_URL if public_url is None else public_url.rstrip("/")

    def _format_message(self, message: ChannelMessage) -> str:
        parts = []
        if message.title:
            parts.append(f"<b>{html.escape(message.title)}</b>")
        if message.body:
            parts.append(html.escape(message.body))
        if message.action_url and self.public_url:
            target = message.action_url
            if target.startswith("/"):
                target = f"{self.public_url}{target}"
            parts.append(f'<a href="{html.escape(target, quote=True)}">AntiTrade</a>')
        return "\n\n".join(parts)

    def send(self, channel: NotificationChannel, message: ChannelMessage) -> SendResult:
        if not self.token:
            raise ChannelError("channel_unavailable")
        if channel.status != "active" or not channel.address:
            raise ChannelError("invalid_recipient")
        url = f"https://api.telegram.org/bot{quote(self.token, safe=':')}/sendMessage"
        payload = {
            "chat_id": channel.address,
            "text": self._format_message(message),
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        try:
            response = httpx.post(url, json=payload, timeout=10.0)
        except httpx.TimeoutException as exc:
            raise ChannelError("unknown_delivery", unknown_delivery=True) from exc
        except httpx.RequestError as exc:
            raise ChannelError("temporary_failure") from exc

        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.is_success and body.get("ok"):
            message_id = body.get("result", {}).get("message_id")
            return SendResult(str(message_id) if message_id is not None else None)

        error_code = int(body.get("error_code") or response.status_code)
        description = str(body.get("description") or "telegram_request_failed")
        if error_code == 429:
            retry_after = body.get("parameters", {}).get("retry_after")
            raise ChannelError("rate_limited", retry_after=int(retry_after or 1))
        if error_code == 403:
            raise ChannelError("recipient_blocked", disable_channel=True)
        if error_code >= 500:
            raise ChannelError("temporary_failure")
        raise ChannelError("invalid_request", description)


class TelegramBindingService:
    def __init__(self, session: Session, adapter: TelegramChannelAdapter | None = None):
        self.session = session
        self.notifications = NotificationService(session)
        self.adapter = adapter or TelegramChannelAdapter()

    def connect(self, user_id: str, locale: str) -> dict[str, str]:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_BOT_USERNAME:
            raise ChannelError("channel_unavailable")
        token = secrets.token_urlsafe(32)
        expires_at = utc_now() + timedelta(minutes=10)
        channel = self.notifications.upsert_pending_channel(
            user_id, "telegram", locale, _token_hash(token), expires_at
        )
        username = TELEGRAM_BOT_USERNAME.lstrip("@")
        return {
            "channel_id": channel.id,
            "deep_link": f"https://t.me/{username}?start={token}",
            "expires_at": expires_at.isoformat(),
        }

    def handle_start(self, payload: dict[str, Any]) -> dict[str, Any]:
        message = payload.get("message") or {}
        text = str(message.get("text") or "")
        parts = text.split(maxsplit=1)
        if len(parts) != 2 or not parts[0].startswith("/start"):
            return {"handled": False}
        token = parts[1].strip()
        channel = self.notifications.find_pending_channel_by_token(_token_hash(token))
        if channel is None:
            return {"handled": False, "reason": "invalid_or_consumed_token"}
        expires_at = parse_utc(channel.verification_expires_at)
        if expires_at is None or expires_at < utc_now():
            return {"handled": False, "reason": "expired_token"}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None or chat.get("type") != "private":
            return {"handled": False, "reason": "private_chat_required"}
        display_name = " ".join(
            value for value in (chat.get("first_name"), chat.get("last_name")) if value
        ) or str(chat.get("username") or "Telegram")
        metadata = {
            "username": chat.get("username"),
            "first_name": chat.get("first_name"),
            "last_name": chat.get("last_name"),
        }
        try:
            self.notifications.activate_channel(channel, str(chat_id), display_name, metadata)
        except IntegrityError:
            self.session.rollback()
            return {"handled": False, "reason": "chat_already_connected"}
        try:
            self.adapter.send(
                channel,
                ChannelMessage(
                    title="AntiTrade",
                    body="Telegram notifications connected successfully. / Telegram 通知已连接。",
                ),
            )
        except ChannelError:
            pass
        return {"handled": True, "channel_id": channel.id}

    def send_test(self, user_id: str, channel_id: str, locale: str) -> SendResult:
        channel = self.notifications.get_channel(user_id, channel_id)
        if channel is None:
            raise ChannelError("channel_not_found")
        if locale == "en":
            message = ChannelMessage("AntiTrade test notification", "Telegram notifications are ready.")
        else:
            message = ChannelMessage("AntiTrade 测试通知", "Telegram 通知已准备就绪。")
        return self.adapter.send(channel, message)

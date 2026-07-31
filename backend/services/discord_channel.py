"""Discord incoming-webhook notification channel."""

from __future__ import annotations

import math
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import APP_PUBLIC_URL
from models import NotificationChannel
from services.notification_channels import ChannelError, ChannelMessage, SendResult
from services.notifications import NotificationService, channel_to_dict

_DISCORD_WEBHOOK_HOSTS = {"discord.com", "canary.discord.com", "ptb.discord.com"}
_DISCORD_WEBHOOK_PATH = re.compile(
    r"^/api(?:/v\d+)?/webhooks/(?P<webhook_id>\d+)/(?P<token>[A-Za-z0-9._-]{20,})/?$"
)


def validate_discord_webhook_url(value: str) -> str:
    """Accept only Discord-owned incoming webhook endpoints."""
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError as exc:
        raise ChannelError("invalid_webhook_url") from exc
    host = (parsed.hostname or "").lower()
    match = _DISCORD_WEBHOOK_PATH.fullmatch(parsed.path)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    valid_query = len(query) <= 1 and all(
        key == "thread_id" and item.isdigit() for key, item in query
    )
    if (
        parsed.scheme != "https"
        or host not in _DISCORD_WEBHOOK_HOSTS
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or match is None
        or not valid_query
    ):
        raise ChannelError("invalid_webhook_url")
    normalized_query = urlencode(query)
    return urlunsplit(("https", host, parsed.path.rstrip("/"), normalized_query, ""))


class DiscordChannelAdapter:
    def __init__(self, public_url: str | None = None):
        self.public_url = APP_PUBLIC_URL if public_url is None else public_url.rstrip("/")

    def _action_url(self, value: str | None) -> str | None:
        if not value:
            return None
        if value.startswith("/") and self.public_url:
            return f"{self.public_url}{value}"
        if value.startswith(("https://", "http://")):
            return value
        return None

    def _payload(self, message: ChannelMessage) -> dict[str, Any]:
        embed: dict[str, Any] = {
            "title": (message.title or "AntiTrade")[:256],
            "description": message.body[:4096],
            "color": 0x5865F2,
        }
        action_url = self._action_url(message.action_url)
        if action_url:
            embed["url"] = action_url
        return {
            "username": "AntiTrade",
            "embeds": [embed],
            "allowed_mentions": {"parse": []},
        }

    def send(self, channel: NotificationChannel, message: ChannelMessage) -> SendResult:
        if channel.status != "active" or not channel.address:
            raise ChannelError("invalid_recipient")
        webhook_url = validate_discord_webhook_url(channel.address)
        parsed = urlsplit(webhook_url)
        request_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["wait"] = "true"
        try:
            response = httpx.post(
                request_url,
                params=query,
                json=self._payload(message),
                timeout=10.0,
            )
        except httpx.TimeoutException as exc:
            raise ChannelError("unknown_delivery", unknown_delivery=True) from exc
        except httpx.RequestError as exc:
            raise ChannelError("temporary_failure") from exc

        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.is_success:
            message_id = body.get("id")
            return SendResult(str(message_id) if message_id is not None else None)
        if response.status_code == 429:
            retry_after = float(body.get("retry_after") or 1)
            raise ChannelError("rate_limited", retry_after=max(1, math.ceil(retry_after)))
        if response.status_code in {401, 403, 404}:
            raise ChannelError("recipient_blocked", disable_channel=True)
        if response.status_code >= 500:
            raise ChannelError("temporary_failure")
        raise ChannelError("invalid_request", str(body.get("message") or "discord_request_failed"))


class DiscordBindingService:
    def __init__(self, session: Session):
        self.session = session
        self.notifications = NotificationService(session)

    def connect(self, user_id: str, webhook_url: str, locale: str) -> dict[str, Any]:
        normalized_url = validate_discord_webhook_url(webhook_url)
        parsed = urlsplit(normalized_url)
        lookup_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        try:
            response = httpx.get(lookup_url, timeout=10.0)
        except httpx.RequestError as exc:
            raise ChannelError("temporary_failure") from exc

        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code == 429:
            retry_after = float(body.get("retry_after") or 1)
            raise ChannelError("rate_limited", retry_after=max(1, math.ceil(retry_after)))
        if response.status_code >= 500:
            raise ChannelError("temporary_failure")
        if not response.is_success or body.get("type") != 1:
            raise ChannelError("invalid_webhook")

        metadata = {
            "webhook_id": str(body.get("id") or ""),
            "guild_id": str(body.get("guild_id") or ""),
            "channel_id": str(body.get("channel_id") or ""),
        }
        try:
            channel = self.notifications.upsert_active_channel(
                user_id=user_id,
                channel_type="discord",
                locale=locale,
                address=normalized_url,
                name=str(body.get("name") or "Discord Webhook"),
                metadata=metadata,
            )
        except IntegrityError as exc:
            self.session.rollback()
            raise ChannelError("webhook_in_use") from exc
        return channel_to_dict(channel)

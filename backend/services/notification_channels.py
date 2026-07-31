"""Channel adapter contract and explicit adapter registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from models import NotificationChannel


@dataclass(frozen=True)
class ChannelMessage:
    title: str
    body: str
    action_url: str | None = None


@dataclass(frozen=True)
class SendResult:
    provider_message_id: str | None = None


class ChannelError(Exception):
    def __init__(
        self,
        code: str,
        message: str = "",
        *,
        retry_after: int | None = None,
        disable_channel: bool = False,
        unknown_delivery: bool = False,
    ):
        super().__init__(message or code)
        self.code = code
        self.safe_message = (message or code)[:300]
        self.retry_after = retry_after
        self.disable_channel = disable_channel
        self.unknown_delivery = unknown_delivery


class ChannelAdapter(Protocol):
    def send(self, channel: NotificationChannel, message: ChannelMessage) -> SendResult: ...


def get_channel_adapters() -> dict[str, ChannelAdapter]:
    from services.discord_channel import DiscordChannelAdapter
    from services.in_app_channel import InAppChannelAdapter
    from services.telegram_channel import TelegramChannelAdapter

    return {
        "in_app": InAppChannelAdapter(),
        "telegram": TelegramChannelAdapter(),
        "discord": DiscordChannelAdapter(),
    }

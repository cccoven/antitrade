import httpx
import pytest
from sqlalchemy import select

from models import NotificationChannel
from services.discord_channel import (
    DiscordBindingService,
    DiscordChannelAdapter,
    validate_discord_webhook_url,
)
from services.notification_channels import ChannelError, ChannelMessage

WEBHOOK_URL = (
    "https://discord.com/api/webhooks/123456789012345678/"
    "abcdefghijklmnopqrstuvwxyz_ABCDEFGHIJKLMNOPQRSTUVWXYZ-123456"
)


def test_discord_webhook_validation_rejects_non_discord_hosts():
    with pytest.raises(ChannelError) as exc_info:
        validate_discord_webhook_url(
            "https://discord.com.evil.test/api/webhooks/123456789/abcdefghijklmnopqrstuvwxyz"
        )

    assert exc_info.value.code == "invalid_webhook_url"


def test_discord_adapter_sends_embed_and_disables_mentions(monkeypatch, db, user_id):
    channel = NotificationChannel(
        id="discord-channel",
        user_id=user_id,
        channel_type="discord",
        name="Alerts",
        status="active",
        address=f"{WEBHOOK_URL}?thread_id=987654321",
        channel_metadata={},
        locale="zh",
        verification_token_hash=None,
        verification_expires_at=None,
        last_error_code=None,
        last_error_at=None,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    db.add(channel)
    db.commit()
    captured = {}

    def fake_post(url, params, json, timeout):
        captured.update({"url": url, "params": params, "json": json, "timeout": timeout})
        return httpx.Response(200, json={"id": "message-7"})

    monkeypatch.setattr(httpx, "post", fake_post)
    result = DiscordChannelAdapter(public_url="https://app.test").send(
        channel,
        ChannelMessage("Market opened", "@everyone NQ is open", "/market-hours"),
    )

    assert result.provider_message_id == "message-7"
    assert captured["url"] == WEBHOOK_URL
    assert captured["params"] == {"thread_id": "987654321", "wait": "true"}
    assert captured["json"]["allowed_mentions"] == {"parse": []}
    assert captured["json"]["embeds"][0]["url"] == "https://app.test/market-hours"


def test_discord_adapter_maps_rate_limit(monkeypatch, db, user_id):
    channel = NotificationChannel(
        id="discord-rate-limit",
        user_id=user_id,
        channel_type="discord",
        name="Alerts",
        status="active",
        address=WEBHOOK_URL,
        channel_metadata={},
        locale="en",
        verification_token_hash=None,
        verification_expires_at=None,
        last_error_code=None,
        last_error_at=None,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    db.add(channel)
    db.commit()
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(429, json={"retry_after": 2.2}),
    )

    with pytest.raises(ChannelError) as exc_info:
        DiscordChannelAdapter().send(channel, ChannelMessage("T", "B"))

    assert exc_info.value.code == "rate_limited"
    assert exc_info.value.retry_after == 3


def test_discord_connect_verifies_webhook_and_hides_secret(monkeypatch, db, user_id):
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: httpx.Response(
            200,
            json={
                "id": "123456789012345678",
                "type": 1,
                "name": "Trading alerts",
                "guild_id": "guild-1",
                "channel_id": "channel-1",
            },
        ),
    )

    result = DiscordBindingService(db).connect(user_id, WEBHOOK_URL, "zh")

    channel = db.execute(
        select(NotificationChannel).where(NotificationChannel.channel_type == "discord")
    ).scalar_one()
    assert channel.address == WEBHOOK_URL
    assert channel.name == "Trading alerts"
    assert result["address"] is None
    assert WEBHOOK_URL not in str(result)

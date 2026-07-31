from datetime import timedelta

import httpx

from services.notification_channels import ChannelError, ChannelMessage
from services.notifications import NotificationService, utc_iso, utc_now
from services.telegram_channel import (
    TelegramBindingService,
    TelegramChannelAdapter,
    _token_hash,
)


def test_telegram_adapter_escapes_html(monkeypatch, db, user_id):
    channel = NotificationService(db).upsert_pending_channel(
        user_id, "telegram", "zh", "hash", utc_now() + timedelta(minutes=10)
    )
    NotificationService(db).activate_channel(channel, "123", "T", {})
    captured = {}

    def fake_post(url, json, timeout):
        captured.update(json)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    monkeypatch.setattr(httpx, "post", fake_post)
    result = TelegramChannelAdapter(token="token", public_url="https://app.test").send(
        channel, ChannelMessage("<Title>", "A & B", "/market-hours")
    )

    assert result.provider_message_id == "7"
    assert "&lt;Title&gt;" in captured["text"]
    assert "A &amp; B" in captured["text"]
    assert 'href="https://app.test/market-hours"' in captured["text"]


def test_telegram_adapter_maps_rate_limit(monkeypatch, db, user_id):
    channel = NotificationService(db).upsert_pending_channel(
        user_id, "telegram", "zh", "hash", utc_now() + timedelta(minutes=10)
    )
    NotificationService(db).activate_channel(channel, "123", "T", {})
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(
            429,
            json={"ok": False, "error_code": 429, "parameters": {"retry_after": 9}},
        ),
    )

    try:
        TelegramChannelAdapter(token="token").send(channel, ChannelMessage("T", "B"))
    except ChannelError as exc:
        assert exc.code == "rate_limited"
        assert exc.retry_after == 9
    else:
        raise AssertionError("rate limit should raise")


def test_start_token_activates_once(db, user_id):
    token = "connect-token"
    channel = NotificationService(db).upsert_pending_channel(
        user_id, "telegram", "zh", _token_hash(token), utc_now() + timedelta(minutes=10)
    )

    class WelcomeAdapter:
        def send(self, channel, message):
            return type("Result", (), {"provider_message_id": "1"})()

    service = TelegramBindingService(db, adapter=WelcomeAdapter())
    payload = {
        "message": {
            "text": f"/start {token}",
            "chat": {"id": 42, "type": "private", "first_name": "Alice"},
        }
    }

    first = service.handle_start(payload)
    second = service.handle_start(payload)

    assert first["handled"] is True
    assert second["handled"] is False
    db.refresh(channel)
    assert channel.status == "active"
    assert channel.address == "42"
    assert channel.verification_token_hash is None

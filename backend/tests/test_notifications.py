from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from models import NotificationChannel, NotificationDelivery, NotificationEvent
from services.notification_channels import ChannelError, SendResult
from services.notification_dispatch import dispatch_pending
from services.in_app_channel import InAppChannelAdapter
from services.notifications import (
    NotificationContent,
    NotificationEventInput,
    NotificationService,
    utc_iso,
)


class FakeAdapter:
    def __init__(self, error: ChannelError | None = None):
        self.error = error
        self.messages = []

    def send(self, channel, message):
        self.messages.append((channel, message))
        if self.error:
            raise self.error
        return SendResult("provider-1")


def _active_channel(db, user_id, locale="zh"):
    now = utc_iso()
    row = NotificationChannel(
        id=f"channel-{user_id}",
        user_id=user_id,
        channel_type="telegram",
        name="Telegram",
        status="active",
        address=f"chat-{user_id}",
        channel_metadata={},
        locale=locale,
        verification_token_hash=None,
        verification_expires_at=None,
        last_error_code=None,
        last_error_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    return row


def _event(key="event-1", event_type="test.ready", expires_at=None):
    now = datetime.now(timezone.utc)
    return NotificationEventInput(
        event_key=key,
        event_type=event_type,
        source="tests",
        subject_type="thing",
        subject_id="one",
        occurred_at=now,
        expires_at=expires_at or now + timedelta(minutes=10),
        content={
            "zh": NotificationContent("测试", "正文"),
            "en": NotificationContent("Test", "Body"),
        },
    )


def test_publish_is_idempotent_and_not_market_specific(db, user_id):
    channel = _active_channel(db, user_id)
    service = NotificationService(db)
    service.upsert_subscription(
        user_id, channel.id, "test.ready", "thing", "one", True, "zh"
    )

    first = service.publish(_event())
    second = service.publish(_event())

    assert first["created"] is True
    assert second["created"] is False
    assert db.scalar(select(func.count()).select_from(NotificationEvent)) == 1
    assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 1


def test_publish_matches_exact_enabled_subscription(db, user_id):
    channel = _active_channel(db, user_id)
    service = NotificationService(db)
    service.upsert_subscription(
        user_id, channel.id, "test.ready", "thing", "different", True, "zh"
    )

    result = service.publish(_event())

    assert result["delivery_count"] == 0


def test_dispatch_sends_localized_message(db, user_id):
    channel = _active_channel(db, user_id, locale="en")
    service = NotificationService(db)
    service.upsert_subscription(
        user_id, channel.id, "test.ready", "thing", "one", True, "en"
    )
    service.publish(_event())
    adapter = FakeAdapter()

    result = dispatch_pending(db, adapters={"telegram": adapter})

    assert result["sent"] == 1
    assert adapter.messages[0][1].title == "Test"
    delivery = db.execute(select(NotificationDelivery)).scalar_one()
    assert delivery.status == "sent"
    assert delivery.provider_message_id == "provider-1"


def test_new_channel_copies_existing_enabled_subscriptions(db, user_id):
    telegram = _active_channel(db, user_id)
    service = NotificationService(db)
    service.upsert_subscription(
        user_id, telegram.id, "test.ready", "thing", "one", True, "zh"
    )

    discord = service.upsert_active_channel(
        user_id=user_id,
        channel_type="discord",
        locale="en",
        address="https://discord.com/api/webhooks/123/token",
        name="Discord",
        metadata={},
    )

    subscriptions = service.list_subscriptions(user_id)
    copied = next(item for item in subscriptions if item["channel_id"] == discord.id)
    assert copied["event_type"] == "test.ready"
    assert copied["subject_id"] == "one"
    assert copied["enabled"] is True
    assert copied["locale"] == "en"


def test_new_channel_does_not_copy_task_scoped_subscription(db, user_id):
    telegram = _active_channel(db, user_id)
    service = NotificationService(db)
    service.sync_subject_subscriptions(
        user_id=user_id,
        subject_type="automation_task",
        subject_id="task-one",
        channel_id=telegram.id,
        event_types={"agent.risk.warning"},
        locale="zh",
    )

    discord = service.upsert_active_channel(
        user_id=user_id,
        channel_type="discord",
        locale="en",
        address="https://discord.com/api/webhooks/456/token",
        name="Discord",
        metadata={},
    )

    assert not any(
        item["channel_id"] == discord.id
        and item["subject_type"] == "automation_task"
        for item in service.list_subscriptions(user_id)
    )


def test_dispatch_expires_stale_event_without_sending(db, user_id):
    channel = _active_channel(db, user_id)
    service = NotificationService(db)
    service.upsert_subscription(
        user_id, channel.id, "test.ready", "thing", "one", True, "zh"
    )
    service.publish(_event(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    adapter = FakeAdapter()

    result = dispatch_pending(db, adapters={"telegram": adapter})

    assert result["expired"] == 1
    assert adapter.messages == []


def test_dispatch_disables_blocked_channel(db, user_id):
    channel = _active_channel(db, user_id)
    service = NotificationService(db)
    service.upsert_subscription(
        user_id, channel.id, "test.ready", "thing", "one", True, "zh"
    )
    service.publish(_event())
    adapter = FakeAdapter(ChannelError("recipient_blocked", disable_channel=True))

    result = dispatch_pending(db, adapters={"telegram": adapter})

    assert result["failed"] == 1
    db.refresh(channel)
    assert channel.status == "disabled"


def test_in_app_channel_delivers_localized_unread_message(db, user_id):
    service = NotificationService(db)
    channel = service.ensure_in_app_channel(user_id, "zh")
    service.upsert_subscription(
        user_id, channel.id, "test.ready", "thing", "one", True, "zh"
    )
    service.publish(_event())

    result = dispatch_pending(db, adapters={"in_app": InAppChannelAdapter()})
    inbox = service.list_inbox(user_id, locale="en")

    assert result["sent"] == 1
    assert inbox["unread_count"] == 1
    assert inbox["next_cursor"] is None
    assert inbox["items"][0]["title"] == "Test"
    assert inbox["items"][0]["body"] == "Body"
    assert inbox["items"][0]["read_at"] is None


def test_in_app_message_read_state_is_idempotent(db, user_id):
    service = NotificationService(db)
    channel = service.ensure_in_app_channel(user_id)
    service.upsert_subscription(
        user_id, channel.id, "test.ready", "thing", "one", True, "zh"
    )
    service.publish(_event())
    dispatch_pending(db, adapters={"in_app": InAppChannelAdapter()})
    delivery = db.execute(select(NotificationDelivery)).scalar_one()

    assert service.mark_inbox_read(user_id, delivery.id) is True
    first_read_at = delivery.read_at
    assert first_read_at is not None
    assert service.mark_inbox_read(user_id, delivery.id) is True
    assert delivery.read_at == first_read_at
    assert service.inbox_unread_count(user_id) == 0


def test_in_app_channel_cannot_be_removed(db, user_id):
    service = NotificationService(db)
    channel = service.ensure_in_app_channel(user_id)

    assert service.remove_channel(user_id, channel.id) is False
    assert service.get_channel(user_id, channel.id) is not None


def test_in_app_message_can_be_deleted(db, user_id):
    service = NotificationService(db)
    channel = service.ensure_in_app_channel(user_id)
    service.upsert_subscription(
        user_id, channel.id, "test.ready", "thing", "one", True, "zh"
    )
    service.publish(_event())
    dispatch_pending(db, adapters={"in_app": InAppChannelAdapter()})
    delivery = db.execute(select(NotificationDelivery)).scalar_one()

    assert service.remove_inbox_message("another-user", delivery.id) is False
    assert service.remove_inbox_message(user_id, delivery.id) is True
    assert service.list_inbox(user_id, locale="zh")["items"] == []


def test_cleanup_removes_old_event_and_delivery_history(db, user_id):
    channel = _active_channel(db, user_id)
    service = NotificationService(db)
    service.upsert_subscription(
        user_id, channel.id, "test.ready", "thing", "one", True, "zh"
    )
    service.publish(_event())
    event = db.execute(select(NotificationEvent)).scalar_one()
    now = datetime.now(timezone.utc)
    event.created_at = utc_iso(now - timedelta(days=31))
    db.commit()

    assert service.cleanup(now=now) == 1
    assert db.scalar(select(func.count()).select_from(NotificationEvent)) == 0
    assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 0

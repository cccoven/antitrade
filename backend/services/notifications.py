"""Generic notification events, channels, subscriptions, and delivery creation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from models import (
    NotificationChannel,
    NotificationDelivery,
    NotificationEvent,
    NotificationSubscription,
)

UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_iso(value: datetime | None = None) -> str:
    current = value or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(UTC).isoformat()


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class NotificationContent:
    title: str
    body: str
    action_url: str | None = None


@dataclass(frozen=True)
class NotificationEventInput:
    event_key: str
    event_type: str
    source: str
    occurred_at: datetime
    content: dict[str, NotificationContent | dict[str, Any]]
    subject_type: str | None = None
    subject_id: str | None = None
    expires_at: datetime | None = None
    data: dict[str, Any] = field(default_factory=dict)


def select_content(content: dict[str, Any], locale: str) -> dict[str, str | None]:
    for key in (locale, "en", "zh"):
        value = content.get(key)
        if isinstance(value, dict):
            return {
                "title": str(value.get("title", "")),
                "body": str(value.get("body", "")),
                "action_url": value.get("action_url"),
            }
    for key in sorted(content):
        value = content[key]
        if isinstance(value, dict):
            return {
                "title": str(value.get("title", "")),
                "body": str(value.get("body", "")),
                "action_url": value.get("action_url"),
            }
    return {"title": "", "body": "", "action_url": None}


def _content_dict(content: NotificationContent | dict[str, Any]) -> dict[str, Any]:
    if isinstance(content, NotificationContent):
        return {
            "title": content.title,
            "body": content.body,
            "action_url": content.action_url,
        }
    return {
        "title": str(content.get("title", "")),
        "body": str(content.get("body", "")),
        "action_url": content.get("action_url"),
    }


def channel_to_dict(row: NotificationChannel) -> dict[str, Any]:
    return {
        "id": row.id,
        "channel_type": row.channel_type,
        "name": row.name,
        "status": row.status,
        # Discord webhook URLs are credentials and must never be returned to clients.
        "address": None if row.channel_type == "discord" else row.address,
        "metadata": row.channel_metadata or {},
        "locale": row.locale,
        "last_error_code": row.last_error_code,
        "last_error_at": row.last_error_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def subscription_to_dict(row: NotificationSubscription) -> dict[str, Any]:
    return {
        "id": row.id,
        "channel_id": row.channel_id,
        "event_type": row.event_type,
        "subject_type": row.subject_type or None,
        "subject_id": row.subject_id or None,
        "enabled": row.enabled,
        "locale": row.locale,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


class NotificationService:
    def __init__(self, session: Session):
        self.session = session

    def ensure_in_app_channel(
        self,
        user_id: str,
        locale: str = "zh",
    ) -> NotificationChannel:
        normalized_locale = locale if locale in {"zh", "en"} else "zh"
        existing = self.session.execute(
            select(NotificationChannel).where(
                NotificationChannel.user_id == user_id,
                NotificationChannel.channel_type == "in_app",
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.status != "active":
                existing.status = "active"
                existing.address = None
                existing.last_error_code = None
                existing.last_error_at = None
                existing.updated_at = utc_iso()
                self.session.commit()
            return existing

        now = utc_iso()
        channel_id = str(uuid.uuid4())
        inserted_id = self.session.execute(
            pg_insert(NotificationChannel)
            .values(
                id=channel_id,
                user_id=user_id,
                channel_type="in_app",
                name="In-app",
                status="active",
                address=None,
                channel_metadata={"builtin": True},
                locale=normalized_locale,
                verification_token_hash=None,
                verification_expires_at=None,
                last_error_code=None,
                last_error_at=None,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(constraint="uq_notification_channels_user_type")
            .returning(NotificationChannel.id)
        ).scalar_one_or_none()
        self.session.commit()

        row = self.session.execute(
            select(NotificationChannel).where(
                NotificationChannel.user_id == user_id,
                NotificationChannel.channel_type == "in_app",
            )
        ).scalar_one()
        if inserted_id is not None:
            self.copy_enabled_subscriptions(user_id, row.id, normalized_locale)
        return row

    def list_channels(self, user_id: str, locale: str = "zh") -> list[dict[str, Any]]:
        self.ensure_in_app_channel(user_id, locale)
        rows = self.session.execute(
            select(NotificationChannel)
            .where(NotificationChannel.user_id == user_id)
            .order_by(NotificationChannel.created_at)
        ).scalars().all()
        return [channel_to_dict(row) for row in rows]

    def get_channel(self, user_id: str, channel_id: str) -> NotificationChannel | None:
        return self.session.execute(
            select(NotificationChannel).where(
                NotificationChannel.id == channel_id,
                NotificationChannel.user_id == user_id,
            )
        ).scalar_one_or_none()

    def upsert_pending_channel(
        self,
        user_id: str,
        channel_type: str,
        locale: str,
        token_hash: str,
        expires_at: datetime,
    ) -> NotificationChannel:
        now = utc_iso()
        row = self.session.execute(
            select(NotificationChannel).where(
                NotificationChannel.user_id == user_id,
                NotificationChannel.channel_type == channel_type,
            )
        ).scalar_one_or_none()
        if row is None:
            row = NotificationChannel(
                id=str(uuid.uuid4()),
                user_id=user_id,
                channel_type=channel_type,
                name=channel_type.title(),
                status="pending",
                address=None,
                channel_metadata={},
                locale=locale,
                verification_token_hash=token_hash,
                verification_expires_at=utc_iso(expires_at),
                last_error_code=None,
                last_error_at=None,
                created_at=now,
                updated_at=now,
            )
            self.session.add(row)
        else:
            row.status = "pending"
            row.address = None
            row.locale = locale
            row.verification_token_hash = token_hash
            row.verification_expires_at = utc_iso(expires_at)
            row.last_error_code = None
            row.last_error_at = None
            row.updated_at = now
        self.session.commit()
        return row

    def find_pending_channel_by_token(self, token_hash: str) -> NotificationChannel | None:
        return self.session.execute(
            select(NotificationChannel).where(
                NotificationChannel.channel_type == "telegram",
                NotificationChannel.status == "pending",
                NotificationChannel.verification_token_hash == token_hash,
            )
        ).scalar_one_or_none()

    def activate_channel(
        self,
        row: NotificationChannel,
        address: str,
        name: str,
        metadata: dict[str, Any],
    ) -> NotificationChannel:
        row.status = "active"
        row.address = address
        row.name = name
        row.channel_metadata = metadata
        row.verification_token_hash = None
        row.verification_expires_at = None
        row.last_error_code = None
        row.last_error_at = None
        row.updated_at = utc_iso()
        self.session.commit()
        self.copy_enabled_subscriptions(row.user_id, row.id, row.locale)
        return row

    def upsert_active_channel(
        self,
        *,
        user_id: str,
        channel_type: str,
        locale: str,
        address: str,
        name: str,
        metadata: dict[str, Any],
    ) -> NotificationChannel:
        row = self.session.execute(
            select(NotificationChannel).where(
                NotificationChannel.user_id == user_id,
                NotificationChannel.channel_type == channel_type,
            )
        ).scalar_one_or_none()
        now = utc_iso()
        if row is None:
            row = NotificationChannel(
                id=str(uuid.uuid4()),
                user_id=user_id,
                channel_type=channel_type,
                name=name,
                status="active",
                address=address,
                channel_metadata=metadata,
                locale=locale,
                verification_token_hash=None,
                verification_expires_at=None,
                last_error_code=None,
                last_error_at=None,
                created_at=now,
                updated_at=now,
            )
            self.session.add(row)
        else:
            row.name = name
            row.status = "active"
            row.address = address
            row.channel_metadata = metadata
            row.locale = locale
            row.verification_token_hash = None
            row.verification_expires_at = None
            row.last_error_code = None
            row.last_error_at = None
            row.updated_at = now
        self.session.commit()
        self.copy_enabled_subscriptions(user_id, row.id, locale)
        return row

    def copy_enabled_subscriptions(self, user_id: str, channel_id: str, locale: str) -> int:
        """Copy active targets from the user's other channels to a newly connected channel."""
        rows = self.session.execute(
            select(
                NotificationSubscription.event_type,
                NotificationSubscription.subject_type,
                NotificationSubscription.subject_id,
            )
            .where(
                NotificationSubscription.user_id == user_id,
                NotificationSubscription.channel_id != channel_id,
                NotificationSubscription.subject_type != "automation_task",
                NotificationSubscription.enabled.is_(True),
            )
            .distinct()
        ).all()
        now = utc_iso()
        for event_type, subject_type, subject_id in rows:
            stmt = pg_insert(NotificationSubscription).values(
                id=str(uuid.uuid4()),
                user_id=user_id,
                channel_id=channel_id,
                event_type=event_type,
                subject_type=subject_type,
                subject_id=subject_id,
                enabled=True,
                locale=locale,
                created_at=now,
                updated_at=now,
            )
            self.session.execute(
                stmt.on_conflict_do_update(
                    constraint="uq_notification_subscriptions_target",
                    set_={"enabled": True, "locale": locale, "updated_at": now},
                )
            )
        self.session.commit()
        return len(rows)

    def remove_channel(self, user_id: str, channel_id: str) -> bool:
        result = self.session.execute(
            delete(NotificationChannel).where(
                NotificationChannel.id == channel_id,
                NotificationChannel.user_id == user_id,
                NotificationChannel.channel_type != "in_app",
            )
        )
        self.session.commit()
        return bool(result.rowcount)

    def list_subscriptions(self, user_id: str) -> list[dict[str, Any]]:
        self.ensure_in_app_channel(user_id)
        rows = self.session.execute(
            select(NotificationSubscription)
            .where(NotificationSubscription.user_id == user_id)
            .order_by(NotificationSubscription.created_at)
        ).scalars().all()
        return [subscription_to_dict(row) for row in rows]

    def upsert_subscription(
        self,
        user_id: str,
        channel_id: str,
        event_type: str,
        subject_type: str | None,
        subject_id: str | None,
        enabled: bool,
        locale: str,
    ) -> dict[str, Any] | None:
        channel = self.get_channel(user_id, channel_id)
        if channel is None:
            return None
        now = utc_iso()
        values = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "channel_id": channel_id,
            "event_type": event_type,
            "subject_type": subject_type or "",
            "subject_id": subject_id or "",
            "enabled": enabled,
            "locale": locale,
            "created_at": now,
            "updated_at": now,
        }
        stmt = pg_insert(NotificationSubscription).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_notification_subscriptions_target",
            set_={"enabled": enabled, "locale": locale, "updated_at": now},
        ).returning(NotificationSubscription)
        row = self.session.execute(stmt).scalar_one()
        self.session.commit()
        return subscription_to_dict(row)

    def remove_subscription(self, user_id: str, subscription_id: str) -> bool:
        result = self.session.execute(
            delete(NotificationSubscription).where(
                NotificationSubscription.id == subscription_id,
                NotificationSubscription.user_id == user_id,
            )
        )
        self.session.commit()
        return bool(result.rowcount)

    def sync_subject_subscriptions(
        self,
        *,
        user_id: str,
        subject_type: str,
        subject_id: str,
        channel_id: str | None,
        event_types: set[str],
        locale: str,
    ) -> int:
        """Enable one channel for a subject and disable its previous targets."""
        if locale not in {"zh", "en"}:
            raise ValueError("invalid_notification_locale")
        channel = self.get_channel(user_id, channel_id) if channel_id else None
        if channel_id and (channel is None or channel.status != "active"):
            raise ValueError("notification_channel_unavailable")

        now = utc_iso()
        self.session.execute(
            update(NotificationSubscription)
            .where(
                NotificationSubscription.user_id == user_id,
                NotificationSubscription.subject_type == subject_type,
                NotificationSubscription.subject_id == subject_id,
            )
            .values(enabled=False, updated_at=now)
        )
        if channel is not None:
            for event_type in sorted(event_types):
                stmt = pg_insert(NotificationSubscription).values(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    channel_id=channel.id,
                    event_type=event_type,
                    subject_type=subject_type,
                    subject_id=subject_id,
                    enabled=True,
                    locale=locale,
                    created_at=now,
                    updated_at=now,
                )
                self.session.execute(
                    stmt.on_conflict_do_update(
                        constraint="uq_notification_subscriptions_target",
                        set_={"enabled": True, "locale": locale, "updated_at": now},
                    )
                )
        self.session.commit()
        return len(event_types) if channel is not None else 0

    def publish(self, event: NotificationEventInput) -> dict[str, Any]:
        if not event.event_key or not event.event_type or not event.source or not event.content:
            raise ValueError("invalid_notification_event")
        content = {lang: _content_dict(value) for lang, value in event.content.items()}
        if not any(value["title"] or value["body"] for value in content.values()):
            raise ValueError("invalid_notification_content")

        now = utc_iso()
        event_id = str(uuid.uuid4())
        stmt = pg_insert(NotificationEvent).values(
            id=event_id,
            event_key=event.event_key,
            event_type=event.event_type,
            source=event.source,
            subject_type=event.subject_type,
            subject_id=event.subject_id,
            occurred_at=utc_iso(event.occurred_at),
            expires_at=utc_iso(event.expires_at) if event.expires_at else None,
            content=content,
            data=event.data,
            created_at=now,
        ).on_conflict_do_nothing(index_elements=[NotificationEvent.event_key]).returning(
            NotificationEvent.id
        )
        inserted_id = self.session.execute(stmt).scalar_one_or_none()
        if inserted_id is None:
            existing = self.session.execute(
                select(NotificationEvent).where(NotificationEvent.event_key == event.event_key)
            ).scalar_one()
            self.session.commit()
            return {"id": existing.id, "event_key": existing.event_key, "created": False}

        subscriptions = self.session.execute(
            select(NotificationSubscription)
            .join(NotificationChannel, NotificationChannel.id == NotificationSubscription.channel_id)
            .where(
                NotificationSubscription.event_type == event.event_type,
                NotificationSubscription.subject_type == (event.subject_type or ""),
                NotificationSubscription.subject_id == (event.subject_id or ""),
                NotificationSubscription.enabled.is_(True),
                NotificationChannel.status == "active",
            )
        ).scalars().all()
        for subscription in subscriptions:
            delivery_stmt = pg_insert(NotificationDelivery).values(
                id=str(uuid.uuid4()),
                event_id=event_id,
                subscription_id=subscription.id,
                channel_id=subscription.channel_id,
                status="pending",
                attempt_count=0,
                next_attempt_at=now,
                claimed_at=None,
                sent_at=None,
                read_at=None,
                provider_message_id=None,
                last_error_code=None,
                last_error_message=None,
                created_at=now,
                updated_at=now,
            ).on_conflict_do_nothing(constraint="uq_notification_deliveries_target")
            self.session.execute(delivery_stmt)
        self.session.commit()
        return {
            "id": event_id,
            "event_key": event.event_key,
            "created": True,
            "delivery_count": len(subscriptions),
        }

    def list_deliveries(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.session.execute(
            select(NotificationDelivery, NotificationEvent, NotificationSubscription)
            .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
            .join(
                NotificationSubscription,
                NotificationSubscription.id == NotificationDelivery.subscription_id,
            )
            .where(NotificationSubscription.user_id == user_id)
            .order_by(NotificationDelivery.created_at.desc())
            .limit(max(1, min(limit, 100)))
        ).all()
        result = []
        for delivery, event, subscription in rows:
            message = select_content(event.content or {}, subscription.locale)
            result.append({
                "id": delivery.id,
                "event_type": event.event_type,
                "subject_type": event.subject_type,
                "subject_id": event.subject_id,
                "title": message["title"],
                "status": delivery.status,
                "attempt_count": delivery.attempt_count,
                "occurred_at": event.occurred_at,
                "sent_at": delivery.sent_at,
                "last_error_code": delivery.last_error_code,
                "created_at": delivery.created_at,
            })
        return result

    def list_inbox(
        self,
        user_id: str,
        *,
        locale: str,
        unread_only: bool = False,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        self.ensure_in_app_channel(user_id, locale)
        page_size = max(1, min(limit, 50))
        query = (
            select(
                NotificationDelivery,
                NotificationEvent,
            )
            .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
            .join(
                NotificationChannel,
                NotificationChannel.id == NotificationDelivery.channel_id,
            )
            .where(
                NotificationChannel.user_id == user_id,
                NotificationChannel.channel_type == "in_app",
                NotificationDelivery.status == "sent",
            )
        )
        if unread_only:
            query = query.where(NotificationDelivery.read_at.is_(None))
        if cursor:
            cursor_row = self.session.execute(
                select(NotificationDelivery.created_at, NotificationDelivery.id)
                .join(
                    NotificationChannel,
                    NotificationChannel.id == NotificationDelivery.channel_id,
                )
                .where(
                    NotificationDelivery.id == cursor,
                    NotificationChannel.user_id == user_id,
                    NotificationChannel.channel_type == "in_app",
                )
            ).one_or_none()
            if cursor_row is None:
                raise ValueError("notification_inbox_cursor_not_found")
            query = query.where(
                or_(
                    NotificationDelivery.created_at < cursor_row.created_at,
                    and_(
                        NotificationDelivery.created_at == cursor_row.created_at,
                        NotificationDelivery.id < cursor_row.id,
                    ),
                )
            )

        rows = self.session.execute(
            query
            .order_by(
                NotificationDelivery.created_at.desc(),
                NotificationDelivery.id.desc(),
            )
            .limit(page_size + 1)
        ).all()
        has_more = len(rows) > page_size
        page = rows[:page_size]
        items = []
        for delivery, event in page:
            message = select_content(event.content or {}, locale)
            items.append({
                "id": delivery.id,
                "event_type": event.event_type,
                "subject_type": event.subject_type,
                "subject_id": event.subject_id,
                "title": message["title"],
                "body": message["body"],
                "action_url": message["action_url"],
                "occurred_at": event.occurred_at,
                "created_at": delivery.created_at,
                "read_at": delivery.read_at,
            })
        return {
            "items": items,
            "next_cursor": page[-1][0].id if has_more and page else None,
            "unread_count": self.inbox_unread_count(user_id),
        }

    def inbox_unread_count(self, user_id: str) -> int:
        self.ensure_in_app_channel(user_id)
        return int(self.session.scalar(
            select(func.count())
            .select_from(NotificationDelivery)
            .join(
                NotificationChannel,
                NotificationChannel.id == NotificationDelivery.channel_id,
            )
            .where(
                NotificationChannel.user_id == user_id,
                NotificationChannel.channel_type == "in_app",
                NotificationDelivery.status == "sent",
                NotificationDelivery.read_at.is_(None),
            )
        ) or 0)

    def mark_inbox_read(self, user_id: str, delivery_id: str) -> bool:
        delivery = self.session.execute(
            select(NotificationDelivery)
            .join(
                NotificationChannel,
                NotificationChannel.id == NotificationDelivery.channel_id,
            )
            .where(
                NotificationDelivery.id == delivery_id,
                NotificationChannel.user_id == user_id,
                NotificationChannel.channel_type == "in_app",
                NotificationDelivery.status == "sent",
            )
        ).scalar_one_or_none()
        if delivery is None:
            return False
        if delivery.read_at is None:
            now = utc_iso()
            delivery.read_at = now
            delivery.updated_at = now
            self.session.commit()
        return True

    def mark_all_inbox_read(self, user_id: str) -> int:
        now = utc_iso()
        channel_ids = select(NotificationChannel.id).where(
            NotificationChannel.user_id == user_id,
            NotificationChannel.channel_type == "in_app",
        )
        result = self.session.execute(
            update(NotificationDelivery)
            .where(
                NotificationDelivery.channel_id.in_(channel_ids),
                NotificationDelivery.status == "sent",
                NotificationDelivery.read_at.is_(None),
            )
            .values(read_at=now, updated_at=now)
        )
        self.session.commit()
        return int(result.rowcount or 0)

    def remove_inbox_message(self, user_id: str, delivery_id: str) -> bool:
        channel_ids = select(NotificationChannel.id).where(
            NotificationChannel.user_id == user_id,
            NotificationChannel.channel_type == "in_app",
        )
        result = self.session.execute(
            delete(NotificationDelivery).where(
                NotificationDelivery.id == delivery_id,
                NotificationDelivery.channel_id.in_(channel_ids),
            )
        )
        self.session.commit()
        return bool(result.rowcount)

    def cleanup(self, *, retention_days: int = 30, now: datetime | None = None) -> int:
        """Delete expired event/delivery history; channel settings remain untouched."""
        cutoff = utc_iso((now or utc_now()) - timedelta(days=max(1, retention_days)))
        result = self.session.execute(
            delete(NotificationEvent).where(NotificationEvent.created_at < cutoff)
        )
        self.session.commit()
        return int(result.rowcount or 0)

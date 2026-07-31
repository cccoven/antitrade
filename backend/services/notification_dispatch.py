"""Claim and deliver pending notifications through registered channel adapters."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from models import (
    NotificationChannel,
    NotificationDelivery,
    NotificationEvent,
    NotificationSubscription,
)
from services.notification_channels import (
    ChannelAdapter,
    ChannelError,
    ChannelMessage,
    get_channel_adapters,
)
from services.notifications import parse_utc, select_content, utc_iso, utc_now

MAX_ATTEMPTS = 3
PROCESSING_TIMEOUT_SECONDS = 120


def _safe_error(exc: ChannelError) -> str:
    return exc.safe_message[:300]


def dispatch_pending(
    session: Session,
    *,
    limit: int = 50,
    adapters: dict[str, ChannelAdapter] | None = None,
    now=None,
) -> dict[str, int]:
    current = now or utc_now()
    now_value = utc_iso(current)
    stale_before = utc_iso(current - timedelta(seconds=PROCESSING_TIMEOUT_SECONDS))
    session.execute(
        update(NotificationDelivery)
        .where(
            NotificationDelivery.status == "processing",
            NotificationDelivery.claimed_at < stale_before,
        )
        .values(status="unknown", last_error_code="worker_interrupted", updated_at=now_value)
    )
    session.commit()

    rows = session.execute(
        select(NotificationDelivery)
        .where(
            NotificationDelivery.status.in_(("pending", "retrying")),
            NotificationDelivery.next_attempt_at <= now_value,
        )
        .order_by(NotificationDelivery.next_attempt_at, NotificationDelivery.created_at)
        .limit(max(1, min(limit, 100)))
        .with_for_update(skip_locked=True)
    ).scalars().all()
    claimed_ids = []
    for row in rows:
        row.status = "processing"
        row.claimed_at = now_value
        row.attempt_count += 1
        row.updated_at = now_value
        claimed_ids.append(row.id)
    session.commit()

    registry = adapters or get_channel_adapters()
    counts = {"sent": 0, "retrying": 0, "failed": 0, "expired": 0, "unknown": 0}
    for delivery_id in claimed_ids:
        delivery = session.get(NotificationDelivery, delivery_id)
        if delivery is None:
            continue
        event = session.get(NotificationEvent, delivery.event_id)
        subscription = session.get(NotificationSubscription, delivery.subscription_id)
        channel = session.get(NotificationChannel, delivery.channel_id)
        if event is None or subscription is None or channel is None:
            delivery.status = "failed"
            delivery.last_error_code = "delivery_target_missing"
            delivery.updated_at = utc_iso()
            session.commit()
            counts["failed"] += 1
            continue

        finished_at = utc_now()
        expires_at = parse_utc(event.expires_at)
        if expires_at is not None and expires_at <= finished_at:
            delivery.status = "expired"
            delivery.last_error_code = "event_expired"
            delivery.updated_at = utc_iso(finished_at)
            session.commit()
            counts["expired"] += 1
            continue
        if channel.status != "active":
            delivery.status = "failed"
            delivery.last_error_code = "channel_inactive"
            delivery.updated_at = utc_iso(finished_at)
            session.commit()
            counts["failed"] += 1
            continue
        adapter = registry.get(channel.channel_type)
        if adapter is None:
            delivery.status = "failed"
            delivery.last_error_code = "channel_unavailable"
            delivery.updated_at = utc_iso(finished_at)
            session.commit()
            counts["failed"] += 1
            continue

        content = select_content(event.content or {}, subscription.locale)
        message = ChannelMessage(
            title=str(content["title"] or ""),
            body=str(content["body"] or ""),
            action_url=content["action_url"],
        )
        try:
            result = adapter.send(channel, message)
        except ChannelError as exc:
            failed_at = utc_now()
            delivery.last_error_code = exc.code
            delivery.last_error_message = _safe_error(exc)
            delivery.updated_at = utc_iso(failed_at)
            if exc.disable_channel:
                channel.status = "disabled"
                channel.last_error_code = exc.code
                channel.last_error_at = utc_iso(failed_at)
                channel.updated_at = utc_iso(failed_at)
            if exc.unknown_delivery:
                delivery.status = "unknown"
                counts["unknown"] += 1
            elif exc.code in {"rate_limited", "temporary_failure"} and delivery.attempt_count < MAX_ATTEMPTS:
                delay = max(1, exc.retry_after or 2 ** delivery.attempt_count)
                next_attempt = failed_at + timedelta(seconds=delay)
                if expires_at is None or next_attempt < expires_at:
                    delivery.status = "retrying"
                    delivery.next_attempt_at = utc_iso(next_attempt)
                    counts["retrying"] += 1
                else:
                    delivery.status = "expired"
                    counts["expired"] += 1
            else:
                delivery.status = "failed"
                counts["failed"] += 1
            session.commit()
            continue
        except Exception:
            delivery.status = "unknown"
            delivery.last_error_code = "unexpected_channel_error"
            delivery.last_error_message = "unexpected channel error"
            delivery.updated_at = utc_iso()
            session.commit()
            counts["unknown"] += 1
            continue

        sent_at = utc_iso()
        delivery.status = "sent"
        delivery.sent_at = sent_at
        delivery.provider_message_id = result.provider_message_id
        delivery.last_error_code = None
        delivery.last_error_message = None
        delivery.updated_at = sent_at
        session.commit()
        counts["sent"] += 1
    return counts

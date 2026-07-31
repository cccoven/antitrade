"""Plans, entitlements, usage metering, and Stripe subscription state."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import (
    APP_PUBLIC_URL,
    BILLING_CURRENCY,
    BILLING_FREE_AI_UNITS,
    BILLING_PRO_AI_UNITS,
    BILLING_PRO_MONTHLY_AMOUNT,
    BILLING_PRO_YEARLY_AMOUNT,
    STRIPE_PRO_MONTHLY_PRICE_ID,
    STRIPE_PRO_YEARLY_PRICE_ID,
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
)
from models import BillingAccount, BillingUsageEvent, StripeWebhookEvent, User
from services.stripe_billing import StripeBillingPort


AI_METRIC = "ai_units"

FEATURES_BY_PLAN: dict[str, dict[str, bool]] = {
    "free": {
        "assistant.basic": True,
        "assistant.research": False,
        "assistant.web_search": False,
        "assistant.vision": False,
        "assistant.optimize": True,
        "analysis.run": True,
        "journal.ai_assist": False,
        "recognition.parse": False,
    },
    "pro": {
        "assistant.basic": True,
        "assistant.research": True,
        "assistant.web_search": True,
        "assistant.vision": True,
        "assistant.optimize": True,
        "analysis.run": True,
        "journal.ai_assist": True,
        "recognition.parse": True,
    },
}

CHAT_UNIT_COST = {"quick": 1, "standard": 2, "research": 8}
WEB_SEARCH_UNIT_COST = 2
VISION_UNIT_COST = 2
PROMPT_OPTIMIZE_UNIT_COST = 1
ANALYSIS_UNIT_COST = 4
DAILY_REVIEW_UNIT_COST = 2
RECOGNITION_UNIT_COST = 4


class BillingAccessError(Exception):
    def __init__(self, feature: str, reason: str, usage: dict[str, Any] | None = None):
        super().__init__(reason)
        self.feature = feature
        self.reason = reason
        self.usage = usage


class BillingConfigurationError(Exception):
    pass


class BillingConflictError(Exception):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _timestamp_iso(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _calendar_period(now: datetime) -> tuple[datetime, datetime]:
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 12:
        end = start.replace(year=now.year + 1, month=1)
    else:
        end = start.replace(month=now.month + 1)
    return start, end


def _object_id(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        raw = value.get("id")
        return str(raw) if raw else None
    return None


class BillingModule:
    """Deep module exposing one entitlement and one billing-management interface."""

    def __init__(self, session: Session, stripe_adapter: StripeBillingPort | None = None):
        self.session = session
        self.stripe = stripe_adapter

    def _account(self, user_id: str) -> BillingAccount | None:
        return self.session.get(BillingAccount, user_id)

    def _ensure_account(self, user_id: str) -> BillingAccount:
        account = self._account(user_id)
        if account is not None:
            return account
        now = _iso(_utc_now())
        account = BillingAccount(
            user_id=user_id,
            plan="free",
            status="none",
            cancel_at_period_end=False,
            created_at=now,
            updated_at=now,
        )
        self.session.add(account)
        self.session.flush()
        return account

    @staticmethod
    def _has_pro_access(account: BillingAccount | None, now: datetime) -> bool:
        if account is None or account.plan != "pro":
            return False
        if account.status in {"active", "trialing"}:
            return True
        if account.status != "past_due" or not account.current_period_end:
            return False
        try:
            return datetime.fromisoformat(account.current_period_end) > now
        except ValueError:
            return False

    def _plan(self, user_id: str, now: datetime) -> str:
        return "pro" if self._has_pro_access(self._account(user_id), now) else "free"

    def _usage(self, user_id: str, plan: str, now: datetime) -> dict[str, Any]:
        start, end = _calendar_period(now)
        used = self.session.execute(
            select(func.coalesce(func.sum(BillingUsageEvent.units), 0)).where(
                BillingUsageEvent.user_id == user_id,
                BillingUsageEvent.metric == AI_METRIC,
                BillingUsageEvent.occurred_at >= _iso(start),
                BillingUsageEvent.occurred_at < _iso(end),
            )
        ).scalar_one()
        limit = BILLING_PRO_AI_UNITS if plan == "pro" else BILLING_FREE_AI_UNITS
        used_int = int(used or 0)
        return {
            "metric": AI_METRIC,
            "used": used_int,
            "limit": limit,
            "remaining": max(0, limit - used_int),
            "resets_at": _iso(end),
        }

    def summary(self, user_id: str) -> dict[str, Any]:
        now = _utc_now()
        account = self._account(user_id)
        plan = self._plan(user_id, now)
        return {
            "plan": plan,
            "status": account.status if account else "none",
            "billing_interval": account.billing_interval if account else None,
            "current_period_end": account.current_period_end if account else None,
            "cancel_at_period_end": bool(account.cancel_at_period_end) if account else False,
            "features": FEATURES_BY_PLAN[plan],
            "usage": self._usage(user_id, plan, now),
            "stripe_configured": bool(
                STRIPE_SECRET_KEY
                and STRIPE_WEBHOOK_SECRET
                and STRIPE_PRO_MONTHLY_PRICE_ID
                and STRIPE_PRO_YEARLY_PRICE_ID
                and APP_PUBLIC_URL
            ),
            "prices": {
                "currency": BILLING_CURRENCY,
                "monthly": BILLING_PRO_MONTHLY_AMOUNT,
                "yearly": BILLING_PRO_YEARLY_AMOUNT,
            },
        }

    def require(
        self,
        user_id: str,
        feature: str,
        *,
        units: int = 0,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        now = _utc_now()
        plan = self._plan(user_id, now)
        if not FEATURES_BY_PLAN[plan].get(feature, False):
            raise BillingAccessError(feature, "pro_required", self._usage(user_id, plan, now))
        if units <= 0:
            return self.summary(user_id)

        account = self._ensure_account(user_id)
        self.session.execute(
            select(BillingAccount).where(BillingAccount.user_id == account.user_id).with_for_update()
        ).scalar_one()

        normalized_request_id = request_id or str(uuid4())
        existing = self.session.execute(
            select(BillingUsageEvent.id).where(
                BillingUsageEvent.user_id == user_id,
                BillingUsageEvent.metric == AI_METRIC,
                BillingUsageEvent.request_id == normalized_request_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return self.summary(user_id)

        usage = self._usage(user_id, plan, now)
        if usage["used"] + units > usage["limit"]:
            raise BillingAccessError(feature, "limit_reached", usage)

        self.session.add(BillingUsageEvent(
            id=str(uuid4()),
            user_id=user_id,
            metric=AI_METRIC,
            feature=feature,
            units=units,
            request_id=normalized_request_id,
            occurred_at=_iso(now),
        ))
        self.session.commit()
        return self.summary(user_id)

    def create_checkout(self, user_id: str, interval: str) -> dict[str, str]:
        if interval not in {"month", "year"}:
            raise ValueError("invalid_interval")
        if self.stripe is None or not APP_PUBLIC_URL:
            raise BillingConfigurationError("stripe_not_configured")
        price_id = (
            STRIPE_PRO_MONTHLY_PRICE_ID if interval == "month" else STRIPE_PRO_YEARLY_PRICE_ID
        )
        if not price_id:
            raise BillingConfigurationError("stripe_not_configured")
        if self._plan(user_id, _utc_now()) == "pro":
            raise BillingConflictError("already_subscribed")

        user = self.session.get(User, user_id)
        if user is None:
            raise ValueError("user_not_found")
        account = self._ensure_account(user_id)
        if not account.stripe_customer_id:
            customer = self.stripe.create_customer(
                user_id=user_id, email=user.email, name=user.name
            )
            account.stripe_customer_id = str(customer["id"])
            account.updated_at = _iso(_utc_now())
            self.session.commit()

        settings_url = f"{APP_PUBLIC_URL}/settings?section=billing"
        checkout = self.stripe.create_checkout_session(
            user_id=user_id,
            customer_id=account.stripe_customer_id,
            price_id=price_id,
            interval=interval,
            success_url=f"{settings_url}&checkout=success",
            cancel_url=f"{settings_url}&checkout=cancelled",
        )
        return {"url": str(checkout["url"])}

    def create_portal(self, user_id: str) -> dict[str, str]:
        if self.stripe is None or not APP_PUBLIC_URL:
            raise BillingConfigurationError("stripe_not_configured")
        account = self._account(user_id)
        if account is None or not account.stripe_customer_id:
            raise BillingConflictError("customer_missing")
        portal = self.stripe.create_portal_session(
            customer_id=account.stripe_customer_id,
            return_url=f"{APP_PUBLIC_URL}/settings?section=billing",
        )
        return {"url": str(portal["url"])}

    def handle_stripe_event(self, event: dict[str, Any]) -> bool:
        event_id = str(event.get("id") or "")
        event_type = str(event.get("type") or "")
        if not event_id or not event_type:
            raise ValueError("invalid_stripe_event")
        if self.session.get(StripeWebhookEvent, event_id) is not None:
            return False

        data_object = ((event.get("data") or {}).get("object") or {})
        if event_type == "checkout.session.completed":
            self._apply_checkout(data_object)
        elif event_type in {
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        }:
            self._apply_subscription(data_object)

        self.session.add(StripeWebhookEvent(
            id=event_id,
            event_type=event_type,
            processed_at=_iso(_utc_now()),
        ))
        self.session.commit()
        return True

    def _apply_checkout(self, checkout: dict[str, Any]) -> None:
        metadata = checkout.get("metadata") or {}
        user_id = metadata.get("antitrade_user_id") or checkout.get("client_reference_id")
        subscription_id = _object_id(checkout.get("subscription"))
        customer_id = _object_id(checkout.get("customer"))
        if not user_id or not subscription_id:
            return
        account = self._ensure_account(str(user_id))
        if customer_id:
            account.stripe_customer_id = customer_id
        account.stripe_subscription_id = subscription_id
        if self.stripe is not None:
            self._apply_subscription(self.stripe.retrieve_subscription(subscription_id), str(user_id))

    def _apply_subscription(
        self, subscription: dict[str, Any], explicit_user_id: str | None = None
    ) -> None:
        subscription_id = _object_id(subscription)
        customer_id = _object_id(subscription.get("customer"))
        metadata = subscription.get("metadata") or {}
        user_id = explicit_user_id or metadata.get("antitrade_user_id")

        account: BillingAccount | None = None
        if user_id:
            account = self._ensure_account(str(user_id))
        elif subscription_id:
            account = self.session.execute(
                select(BillingAccount).where(
                    BillingAccount.stripe_subscription_id == subscription_id
                )
            ).scalar_one_or_none()
        if account is None and customer_id:
            account = self.session.execute(
                select(BillingAccount).where(BillingAccount.stripe_customer_id == customer_id)
            ).scalar_one_or_none()
        if account is None:
            return

        items = ((subscription.get("items") or {}).get("data") or [])
        item = items[0] if items else {}
        price = item.get("price") or {}
        recurring = price.get("recurring") or {}
        status = str(subscription.get("status") or "none")
        period_start = subscription.get("current_period_start") or item.get("current_period_start")
        period_end = subscription.get("current_period_end") or item.get("current_period_end")

        account.stripe_customer_id = customer_id or account.stripe_customer_id
        account.stripe_subscription_id = subscription_id or account.stripe_subscription_id
        account.stripe_price_id = _object_id(price)
        account.status = status
        account.billing_interval = (
            recurring.get("interval")
            or metadata.get("billing_interval")
            or account.billing_interval
        )
        account.current_period_start = _timestamp_iso(period_start)
        account.current_period_end = _timestamp_iso(period_end)
        account.cancel_at_period_end = bool(subscription.get("cancel_at_period_end", False))
        account.plan = "pro" if status in {"active", "trialing", "past_due"} else "free"
        account.updated_at = _iso(_utc_now())

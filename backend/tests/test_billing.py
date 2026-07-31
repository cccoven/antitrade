"""Billing module behavior at its public interface."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import services.billing as billing_config
from auth_dependency import get_current_user
from db import get_db
from main import app
from models import BillingAccount, BillingUsageEvent, StripeWebhookEvent
from services.billing import BillingAccessError, BillingModule


class FakeStripeAdapter:
    def __init__(self):
        self.checkout_calls: list[dict] = []
        self.subscription = {
            "id": "sub_test",
            "customer": "cus_test",
            "status": "active",
            "cancel_at_period_end": False,
            "metadata": {"antitrade_user_id": ""},
            "items": {
                "data": [{
                    "current_period_start": 1_700_000_000,
                    "current_period_end": 4_100_000_000,
                    "price": {
                        "id": "price_monthly",
                        "recurring": {"interval": "month"},
                    },
                }],
            },
        }

    def create_customer(self, *, user_id: str, email: str, name: str):
        return {"id": "cus_test"}

    def create_checkout_session(self, **params):
        self.checkout_calls.append(params)
        return {"url": "https://checkout.stripe.test/session"}

    def create_portal_session(self, *, customer_id: str, return_url: str):
        return {"url": "https://billing.stripe.test/portal"}

    def retrieve_subscription(self, subscription_id: str):
        return {**self.subscription, "id": subscription_id}

    def construct_event(self, payload: bytes, signature: str):
        raise NotImplementedError


def _grant_pro(db, user_id: str) -> BillingAccount:
    now = datetime.now(timezone.utc)
    row = BillingAccount(
        user_id=user_id,
        stripe_customer_id="cus_pro",
        stripe_subscription_id="sub_pro",
        stripe_price_id="price_pro",
        plan="pro",
        status="active",
        billing_interval="month",
        current_period_start=now.isoformat(),
        current_period_end=(now + timedelta(days=30)).isoformat(),
        cancel_at_period_end=False,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )
    db.add(row)
    db.commit()
    return row


def test_free_summary_has_basic_ai_and_monthly_allowance(db, user_id, monkeypatch):
    monkeypatch.setattr(billing_config, "BILLING_FREE_AI_UNITS", 7)

    summary = BillingModule(db).summary(user_id)

    assert summary["plan"] == "free"
    assert summary["features"]["assistant.basic"] is True
    assert summary["features"]["assistant.research"] is False
    assert summary["usage"]["limit"] == 7
    assert summary["usage"]["remaining"] == 7


def test_usage_is_idempotent_and_limit_is_enforced(db, user_id, monkeypatch):
    monkeypatch.setattr(billing_config, "BILLING_FREE_AI_UNITS", 3)
    module = BillingModule(db)

    module.require(user_id, "assistant.basic", units=2, request_id="request-1")
    module.require(user_id, "assistant.basic", units=2, request_id="request-1")

    assert module.summary(user_id)["usage"]["used"] == 2
    with pytest.raises(BillingAccessError) as caught:
        module.require(user_id, "assistant.basic", units=2, request_id="request-2")
    assert caught.value.reason == "limit_reached"


def test_pro_unlocks_premium_features(db, user_id, monkeypatch):
    monkeypatch.setattr(billing_config, "BILLING_PRO_AI_UNITS", 99)
    _grant_pro(db, user_id)

    summary = BillingModule(db).summary(user_id)

    assert summary["plan"] == "pro"
    assert summary["features"]["assistant.research"] is True
    assert summary["features"]["assistant.vision"] is True
    assert summary["usage"]["limit"] == 99


def test_free_user_cannot_use_pro_feature(db, user_id):
    with pytest.raises(BillingAccessError) as caught:
        BillingModule(db).require(user_id, "recognition.parse", units=4)
    assert caught.value.feature == "recognition.parse"
    assert caught.value.reason == "pro_required"


def test_checkout_uses_server_side_price_mapping(db, user_id, monkeypatch):
    monkeypatch.setattr(billing_config, "APP_PUBLIC_URL", "https://app.antitrade.test")
    monkeypatch.setattr(billing_config, "STRIPE_PRO_MONTHLY_PRICE_ID", "price_monthly")
    adapter = FakeStripeAdapter()

    result = BillingModule(db, adapter).create_checkout(user_id, "month")

    assert result["url"] == "https://checkout.stripe.test/session"
    assert adapter.checkout_calls[0]["price_id"] == "price_monthly"
    assert adapter.checkout_calls[0]["customer_id"] == "cus_test"


def test_subscription_webhook_is_idempotent(db, user_id):
    adapter = FakeStripeAdapter()
    adapter.subscription["metadata"] = {"antitrade_user_id": user_id}
    event = {
        "id": "evt_one",
        "type": "customer.subscription.updated",
        "data": {"object": adapter.subscription},
    }
    module = BillingModule(db, adapter)

    assert module.handle_stripe_event(event) is True
    assert module.handle_stripe_event(event) is False
    assert module.summary(user_id)["plan"] == "pro"
    assert db.query(StripeWebhookEvent).count() == 1
    assert db.query(BillingUsageEvent).count() == 0


def test_billing_summary_route_is_user_scoped(db, user_id):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user_id
    try:
        with TestClient(app) as client:
            response = client.get("/api/billing/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["data"]["plan"] == "free"

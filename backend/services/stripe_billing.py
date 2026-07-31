"""Stripe adapter at the external billing seam."""

from __future__ import annotations

from typing import Any, Protocol

import stripe

from config import STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET


class StripeBillingPort(Protocol):
    def create_customer(self, *, user_id: str, email: str, name: str) -> dict[str, Any]: ...

    def create_checkout_session(
        self,
        *,
        user_id: str,
        customer_id: str,
        price_id: str,
        interval: str,
        success_url: str,
        cancel_url: str,
    ) -> dict[str, Any]: ...

    def create_portal_session(
        self, *, customer_id: str, return_url: str
    ) -> dict[str, Any]: ...

    def retrieve_subscription(self, subscription_id: str) -> dict[str, Any]: ...

    def construct_event(self, payload: bytes, signature: str) -> dict[str, Any]: ...


def _plain(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict_recursive"):
        return value.to_dict_recursive()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return {key: item for key, item in value.items()}


class StripeBillingAdapter:
    def __init__(self, secret_key: str = STRIPE_SECRET_KEY, webhook_secret: str = STRIPE_WEBHOOK_SECRET):
        if not secret_key:
            raise ValueError("stripe_not_configured")
        self.client = stripe.StripeClient(secret_key)
        self.webhook_secret = webhook_secret

    def create_customer(self, *, user_id: str, email: str, name: str) -> dict[str, Any]:
        customer = self.client.v1.customers.create({
            "email": email,
            "name": name,
            "metadata": {"antitrade_user_id": user_id},
        })
        return _plain(customer)

    def create_checkout_session(
        self,
        *,
        user_id: str,
        customer_id: str,
        price_id: str,
        interval: str,
        success_url: str,
        cancel_url: str,
    ) -> dict[str, Any]:
        checkout = self.client.v1.checkout.sessions.create({
            "mode": "subscription",
            "customer": customer_id,
            "client_reference_id": user_id,
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {
                "antitrade_user_id": user_id,
                "billing_interval": interval,
            },
            "subscription_data": {
                "metadata": {
                    "antitrade_user_id": user_id,
                    "billing_interval": interval,
                },
            },
        })
        return _plain(checkout)

    def create_portal_session(
        self, *, customer_id: str, return_url: str
    ) -> dict[str, Any]:
        portal = self.client.v1.billing_portal.sessions.create({
            "customer": customer_id,
            "return_url": return_url,
        })
        return _plain(portal)

    def retrieve_subscription(self, subscription_id: str) -> dict[str, Any]:
        subscription = self.client.v1.subscriptions.retrieve(subscription_id)
        return _plain(subscription)

    def construct_event(self, payload: bytes, signature: str) -> dict[str, Any]:
        if not self.webhook_secret:
            raise ValueError("stripe_webhook_not_configured")
        event = self.client.construct_event(payload, signature, self.webhook_secret)
        return _plain(event)

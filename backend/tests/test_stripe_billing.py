import hashlib
import hmac
import json
import time

import pytest
import stripe

from services.stripe_billing import StripeBillingAdapter


def _signed_payload(secret: str) -> tuple[bytes, str]:
    payload = json.dumps({
        "id": "evt_test",
        "object": "event",
        "type": "customer.subscription.updated",
        "data": {"object": {"id": "sub_test", "object": "subscription"}},
    }, separators=(",", ":")).encode()
    timestamp = int(time.time())
    digest = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    return payload, f"t={timestamp},v1={digest}"


def test_construct_event_verifies_stripe_signature():
    secret = "whsec_test"
    payload, signature = _signed_payload(secret)
    adapter = StripeBillingAdapter(secret_key="sk_test_placeholder", webhook_secret=secret)

    event = adapter.construct_event(payload, signature)

    assert event["id"] == "evt_test"
    assert event["type"] == "customer.subscription.updated"


def test_construct_event_rejects_invalid_signature():
    payload, _ = _signed_payload("whsec_test")
    adapter = StripeBillingAdapter(
        secret_key="sk_test_placeholder", webhook_secret="whsec_test"
    )

    with pytest.raises(stripe.SignatureVerificationError):
        adapter.construct_event(payload, "t=1,v1=invalid")

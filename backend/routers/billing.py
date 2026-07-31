"""Subscription status, Stripe Checkout, Customer Portal, and webhooks."""

import logging
from typing import Literal

import stripe
from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api_response import error, success
from auth_dependency import get_current_user
from db import get_db
from i18n import get_lang, t
from services.billing import BillingConfigurationError, BillingModule
from services.stripe_billing import StripeBillingAdapter


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    interval: Literal["month", "year"]


def _stripe_module(session: Session) -> BillingModule:
    try:
        adapter = StripeBillingAdapter()
    except ValueError as exc:
        raise BillingConfigurationError(str(exc)) from exc
    return BillingModule(session, adapter)


@router.get("/me")
def get_billing_summary(
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return success(BillingModule(session).summary(user_id))


@router.post("/checkout-session")
def create_checkout_session(
    req: CheckoutRequest,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        return success(_stripe_module(session).create_checkout(user_id, req.interval))
    except stripe.StripeError as exc:
        logger.exception("Stripe Checkout session creation failed", exc_info=exc)
        raise BillingConfigurationError("stripe_unavailable") from exc


@router.post("/portal-session")
def create_portal_session(
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        return success(_stripe_module(session).create_portal(user_id))
    except stripe.StripeError as exc:
        logger.exception("Stripe portal session creation failed", exc_info=exc)
        raise BillingConfigurationError("stripe_unavailable") from exc


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    session: Session = Depends(get_db),
):
    lang = get_lang(request)
    if not stripe_signature:
        return error(t("billing.error.invalid_webhook", lang), code=400, status_code=400)
    try:
        module = _stripe_module(session)
        event = module.stripe.construct_event(await request.body(), stripe_signature)  # type: ignore[union-attr]
        processed = module.handle_stripe_event(event)
        return success({"processed": processed})
    except (stripe.SignatureVerificationError, ValueError):
        return error(t("billing.error.invalid_webhook", lang), code=400, status_code=400)
    except stripe.StripeError as exc:
        logger.exception("Stripe webhook processing failed", exc_info=exc)
        return error(t("billing.error.stripe_unavailable", lang), code=503, status_code=503)

"""Stripe Connect Express helpers. Status is always recomputed from account flags."""
from __future__ import annotations

import logging

import stripe
from django.conf import settings

from .models import Contractor

logger = logging.getLogger(__name__)


def _stripe():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def connect_status_from_account(account: dict) -> str:
    charges = bool(account.get("charges_enabled"))
    details = bool(account.get("details_submitted"))
    if charges and details:
        return Contractor.ConnectStatus.COMPLETE
    if details and not charges:
        return Contractor.ConnectStatus.RESTRICTED
    return Contractor.ConnectStatus.PENDING


def ensure_connect_account(contractor: Contractor) -> Contractor:
    """Create an Express account if missing; leave status as pending until webhook/refresh."""
    s = _stripe()
    if not contractor.stripe_connect_account_id:
        account = s.Account.create(
            type="express",
            email=contractor.email or None,
            capabilities={"transfers": {"requested": True}},
            metadata={"contractor_id": str(contractor.id)},
        )
        contractor.stripe_connect_account_id = account["id"]
        contractor.connect_status = Contractor.ConnectStatus.PENDING
        contractor.save(update_fields=["stripe_connect_account_id", "connect_status"])
    return contractor


def create_account_link(contractor: Contractor) -> str:
    ensure_connect_account(contractor)
    s = _stripe()
    link = s.AccountLink.create(
        account=contractor.stripe_connect_account_id,
        refresh_url=settings.STRIPE_CONNECT_REFRESH_URL,
        return_url=settings.STRIPE_CONNECT_RETURN_URL,
        type="account_onboarding",
    )
    return link["url"]


def apply_account_updated(account: dict) -> Contractor | None:
    account_id = account.get("id")
    if not account_id:
        return None
    try:
        contractor = Contractor.objects.get(stripe_connect_account_id=account_id)
    except Contractor.DoesNotExist:
        logger.info("account.updated for unknown account %s", account_id)
        return None
    new_status = connect_status_from_account(account)
    if contractor.connect_status != new_status:
        contractor.connect_status = new_status
        contractor.save(update_fields=["connect_status"])
    return contractor


def construct_webhook_event(payload: bytes, sig_header: str):
    s = _stripe()
    return s.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)

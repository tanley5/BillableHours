"""Optional live SDK smoke against a running stripe-sim (skipped by default)."""
from __future__ import annotations

import os

import pytest

pytest.importorskip("stripe")
import stripe

SIM_URL = os.environ.get("STRIPE_SIM_URL", "")


@pytest.mark.skipif(not SIM_URL, reason="Set STRIPE_SIM_URL to run Stripe SDK smoke")
def test_official_stripe_sdk_against_sim():
    stripe.api_key = "sk_test_sim"
    stripe.api_base = SIM_URL.rstrip("/")
    acct = stripe.Account.create(
        type="express",
        email="sdk-smoke@example.com",
        capabilities={"transfers": {"requested": True}},
    )
    assert acct["charges_enabled"] is True
    pi = stripe.PaymentIntent.create(
        amount=2500,
        currency="usd",
        capture_method="manual",
        automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
        application_fee_amount=50,
        transfer_data={"destination": acct["id"]},
    )
    assert pi["status"] == "requires_capture"
    captured = stripe.PaymentIntent.capture(pi["id"])
    assert captured["status"] == "succeeded"

"""Ledger math for demo Stripe companion (TDD)."""
from __future__ import annotations

import pytest

from app.ledger import (
    CLIENT_PRESET_CENTS,
    InsufficientFunds,
    LedgerStore,
    InvalidPaymentIntent,
)


@pytest.fixture
def store() -> LedgerStore:
    return LedgerStore()


def test_preset_client_balance(store: LedgerStore):
    snap = store.snapshot()
    assert snap["client"]["available"] == CLIENT_PRESET_CENTS
    assert snap["client"]["held"] == 0
    assert snap["platform"]["available"] == 0
    assert snap["contractors"] == {}


def test_create_account_ready_immediately(store: LedgerStore):
    acct = store.create_account(email="alex@example.com", metadata={"contractor_id": "1"})
    assert acct["id"].startswith("acct_")
    assert acct["charges_enabled"] is True
    assert acct["details_submitted"] is True
    assert acct["type"] == "express"
    assert store.snapshot()["contractors"][acct["id"]]["available"] == 0


def test_payment_intent_holds_client_funds(store: LedgerStore):
    acct = store.create_account(email="c@example.com")
    pi = store.create_payment_intent(
        amount=40_000,
        application_fee_amount=800,
        destination=acct["id"],
        metadata={"sub_job_id": "9"},
    )
    assert pi["id"].startswith("pi_")
    assert pi["status"] == "requires_capture"
    assert pi["capture_method"] == "manual"
    assert pi["client_secret"].startswith(pi["id"])
    snap = store.snapshot()
    assert snap["client"]["available"] == CLIENT_PRESET_CENTS - 40_000
    assert snap["client"]["held"] == 40_000
    assert snap["open_holds"][0]["id"] == pi["id"]


def test_insufficient_funds_rejected(store: LedgerStore):
    acct = store.create_account(email="c@example.com")
    with pytest.raises(InsufficientFunds):
        store.create_payment_intent(
            amount=CLIENT_PRESET_CENTS + 1,
            application_fee_amount=1,
            destination=acct["id"],
        )


def test_capture_splits_fee_to_platform_and_rest_to_contractor(store: LedgerStore):
    acct = store.create_account(email="c@example.com")
    pi = store.create_payment_intent(
        amount=40_000,
        application_fee_amount=800,
        destination=acct["id"],
    )
    captured = store.capture_payment_intent(pi["id"])
    assert captured["status"] == "succeeded"
    snap = store.snapshot()
    assert snap["client"]["held"] == 0
    assert snap["client"]["available"] == CLIENT_PRESET_CENTS - 40_000
    assert snap["platform"]["available"] == 800
    assert snap["contractors"][acct["id"]]["available"] == 39_200
    assert snap["open_holds"] == []


def test_cancel_releases_hold_to_client(store: LedgerStore):
    acct = store.create_account(email="c@example.com")
    pi = store.create_payment_intent(
        amount=10_000,
        application_fee_amount=200,
        destination=acct["id"],
    )
    canceled = store.cancel_payment_intent(pi["id"])
    assert canceled["status"] == "canceled"
    snap = store.snapshot()
    assert snap["client"]["available"] == CLIENT_PRESET_CENTS
    assert snap["client"]["held"] == 0
    assert snap["platform"]["available"] == 0
    assert snap["contractors"][acct["id"]]["available"] == 0


def test_capture_twice_raises(store: LedgerStore):
    acct = store.create_account(email="c@example.com")
    pi = store.create_payment_intent(
        amount=5_000,
        application_fee_amount=100,
        destination=acct["id"],
    )
    store.capture_payment_intent(pi["id"])
    with pytest.raises(InvalidPaymentIntent):
        store.capture_payment_intent(pi["id"])


def test_reset_restores_preset(store: LedgerStore):
    acct = store.create_account(email="c@example.com")
    pi = store.create_payment_intent(
        amount=5_000,
        application_fee_amount=100,
        destination=acct["id"],
    )
    store.capture_payment_intent(pi["id"])
    store.top_up_client(1_000)
    store.reset()
    snap = store.snapshot()
    assert snap["client"]["available"] == CLIENT_PRESET_CENTS
    assert snap["client"]["held"] == 0
    assert snap["platform"]["available"] == 0
    assert snap["contractors"] == {}
    assert snap["open_holds"] == []


def test_top_up_client(store: LedgerStore):
    store.top_up_client(2_500)
    assert store.snapshot()["client"]["available"] == CLIENT_PRESET_CENTS + 2_500

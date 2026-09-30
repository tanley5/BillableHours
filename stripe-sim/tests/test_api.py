"""HTTP API tests for stripe-sim (Stripe-shaped form posts)."""
from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.ledger import CLIENT_PRESET_CENTS
from app.main import app, get_store
from app.webhooks import deliver_event, sign_payload


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_sim")
    monkeypatch.setenv("STRIPE_SIM_WEBHOOK_URL", "")
    get_store().reset()
    with TestClient(app) as c:
        yield c
    get_store().reset()


def test_create_account_via_api(client: TestClient):
    r = client.post(
        "/v1/accounts",
        data={
            "type": "express",
            "email": "alex@example.com",
            "capabilities[transfers][requested]": "true",
            "metadata[contractor_id]": "42",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "account"
    assert body["charges_enabled"] is True
    assert body["details_submitted"] is True
    assert body["id"].startswith("acct_")


def test_account_link_redirects_to_return_url(client: TestClient):
    acct = client.post("/v1/accounts", data={"type": "express", "email": "a@b.com"}).json()
    r = client.post(
        "/v1/account_links",
        data={
            "account": acct["id"],
            "refresh_url": "http://localhost/refresh",
            "return_url": "http://localhost/contractor/connect/return",
            "type": "account_onboarding",
        },
    )
    assert r.status_code == 200
    link = r.json()
    assert link["object"] == "account_link"
    assert "/demo/onboard/" in link["url"]

    follow = client.get(link["url"], follow_redirects=False)
    assert follow.status_code in (302, 303, 307)
    assert follow.headers["location"] == "http://localhost/contractor/connect/return"


def test_payment_intent_create_and_capture(client: TestClient):
    acct = client.post("/v1/accounts", data={"type": "express", "email": "c@x.com"}).json()

    create = client.post(
        "/v1/payment_intents",
        data={
            "amount": "40000",
            "currency": "usd",
            "capture_method": "manual",
            "application_fee_amount": "800",
            "transfer_data[destination]": acct["id"],
            "automatic_payment_methods[enabled]": "true",
            "automatic_payment_methods[allow_redirects]": "never",
            "metadata[sub_job_id]": "1",
        },
    )
    assert create.status_code == 200
    pi = create.json()
    assert pi["status"] == "requires_capture"
    assert pi["amount"] == 40000

    ledgers = client.get("/demo/api/ledgers").json()
    assert ledgers["client"]["held"] == 40000
    assert ledgers["client"]["available"] == CLIENT_PRESET_CENTS - 40000

    cap = client.post(f"/v1/payment_intents/{pi['id']}/capture")
    assert cap.status_code == 200
    assert cap.json()["status"] == "succeeded"
    ledgers = client.get("/demo/api/ledgers").json()
    assert ledgers["platform"]["available"] == 800
    assert ledgers["contractors"][acct["id"]]["available"] == 39200
    assert ledgers["client"]["held"] == 0


def test_cancel_payment_intent_via_api(client: TestClient):
    acct = client.post("/v1/accounts", data={"type": "express"}).json()
    pi = client.post(
        "/v1/payment_intents",
        data={
            "amount": "10000",
            "currency": "usd",
            "capture_method": "manual",
            "application_fee_amount": "200",
            "transfer_data[destination]": acct["id"],
        },
    ).json()
    cancel = client.post(f"/v1/payment_intents/{pi['id']}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "canceled"
    ledgers = client.get("/demo/api/ledgers").json()
    assert ledgers["client"]["available"] == CLIENT_PRESET_CENTS
    assert ledgers["client"]["held"] == 0


def test_insufficient_funds_returns_stripe_error(client: TestClient):
    acct = client.post("/v1/accounts", data={"type": "express"}).json()
    r = client.post(
        "/v1/payment_intents",
        data={
            "amount": str(CLIENT_PRESET_CENTS + 1),
            "currency": "usd",
            "capture_method": "manual",
            "application_fee_amount": "1",
            "transfer_data[destination]": acct["id"],
        },
    )
    assert r.status_code == 400
    err = r.json()["error"]
    assert err["type"] == "card_error"
    assert "insufficient" in err["message"].lower()


def test_demo_reset_and_top_up(client: TestClient):
    client.post("/demo/api/top-up", json={"amount_cents": 5000})
    assert client.get("/demo/api/ledgers").json()["client"]["available"] == CLIENT_PRESET_CENTS + 5000
    client.post("/demo/api/reset")
    assert client.get("/demo/api/ledgers").json()["client"]["available"] == CLIENT_PRESET_CENTS


def test_demo_home_renders(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert "Platform" in r.text
    assert "Client" in r.text
    assert "Contractor" in r.text


def test_webhook_signature_and_delivery():
    payload = b'{"id":"evt_test","type":"payment_intent.amount_capturable_updated"}'
    sig = sign_payload(payload, "whsec_test_sim", timestamp=1_700_000_000)
    expected = hmac.new(
        b"whsec_test_sim",
        b"1700000000." + payload,
        hashlib.sha256,
    ).hexdigest()
    assert sig == f"t=1700000000,v1={expected}"

    delivered = []

    def fake_post(url, content=None, headers=None, timeout=None):
        delivered.append({"url": url, "content": content, "headers": headers})

        class R:
            status_code = 200

        return R()

    with patch("app.webhooks.httpx.post", side_effect=fake_post):
        deliver_event(
            {
                "id": "evt_1",
                "object": "event",
                "type": "payment_intent.amount_capturable_updated",
                "data": {"object": {"id": "pi_x", "status": "requires_capture"}},
            },
            webhook_url="http://api:8000/api/stripe/webhook/",
            webhook_secret="whsec_test_sim",
        )
    assert len(delivered) == 1
    assert delivered[0]["url"] == "http://api:8000/api/stripe/webhook/"
    assert "Stripe-Signature" in delivered[0]["headers"]


def test_create_pi_triggers_webhook_when_configured(client: TestClient, monkeypatch):
    monkeypatch.setenv("STRIPE_SIM_WEBHOOK_URL", "http://api:8000/api/stripe/webhook/")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_sim")
    acct = client.post("/v1/accounts", data={"type": "express"}).json()
    delivered = []

    def fake_post(url, content=None, headers=None, timeout=None):
        delivered.append({"url": url, "type": json.loads(content)["type"]})

        class R:
            status_code = 200

        return R()

    with patch("app.webhooks.httpx.post", side_effect=fake_post):
        client.post(
            "/v1/payment_intents",
            data={
                "amount": "5000",
                "currency": "usd",
                "capture_method": "manual",
                "application_fee_amount": "100",
                "transfer_data[destination]": acct["id"],
            },
        )
    assert any(d["type"] == "payment_intent.amount_capturable_updated" for d in delivered)

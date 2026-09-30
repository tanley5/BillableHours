"""In-memory demo ledgers: Client / Platform / Contractor."""
from __future__ import annotations

import secrets
import threading
import uuid
from typing import Any


CLIENT_PRESET_CENTS = 10_000_000  # $100,000.00


class InsufficientFunds(Exception):
    pass


class InvalidPaymentIntent(Exception):
    pass


class UnknownAccount(Exception):
    pass


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


class LedgerStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._client_available = CLIENT_PRESET_CENTS
            self._client_held = 0
            self._platform_available = 0
            self._contractors: dict[str, dict[str, Any]] = {}
            self._payment_intents: dict[str, dict[str, Any]] = {}
            self._account_links: dict[str, dict[str, str]] = {}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            open_holds = [
                {
                    "id": pi["id"],
                    "amount": pi["amount"],
                    "application_fee_amount": pi["application_fee_amount"],
                    "destination": pi["transfer_data"]["destination"],
                    "status": pi["status"],
                }
                for pi in self._payment_intents.values()
                if pi["status"] == "requires_capture"
            ]
            return {
                "client": {
                    "available": self._client_available,
                    "held": self._client_held,
                },
                "platform": {"available": self._platform_available},
                "contractors": {
                    acct_id: {"available": data["available"], "email": data.get("email")}
                    for acct_id, data in self._contractors.items()
                },
                "open_holds": open_holds,
            }

    def top_up_client(self, amount_cents: int) -> None:
        if amount_cents < 0:
            raise ValueError("amount_cents must be non-negative")
        with self._lock:
            self._client_available += amount_cents

    def create_account(
        self,
        *,
        email: str | None = None,
        metadata: dict | None = None,
        type: str = "express",
    ) -> dict[str, Any]:
        with self._lock:
            acct_id = _id("acct")
            account = {
                "id": acct_id,
                "object": "account",
                "type": type or "express",
                "email": email,
                "charges_enabled": True,
                "details_submitted": True,
                "capabilities": {"transfers": "active"},
                "metadata": metadata or {},
            }
            self._contractors[acct_id] = {
                "available": 0,
                "email": email,
                "account": account,
            }
            return dict(account)

    def get_account(self, account_id: str) -> dict[str, Any]:
        with self._lock:
            if account_id not in self._contractors:
                raise UnknownAccount(account_id)
            return dict(self._contractors[account_id]["account"])

    def create_account_link(
        self,
        *,
        account: str,
        return_url: str,
        refresh_url: str,
        public_base: str,
    ) -> dict[str, Any]:
        with self._lock:
            if account not in self._contractors:
                raise UnknownAccount(account)
            token = secrets.token_hex(12)
            self._account_links[token] = {
                "account": account,
                "return_url": return_url,
                "refresh_url": refresh_url,
            }
            return {
                "object": "account_link",
                "url": f"{public_base.rstrip('/')}/demo/onboard/{token}",
                "created": 0,
                "expires_at": 0,
            }

    def consume_account_link(self, token: str) -> dict[str, str] | None:
        with self._lock:
            return self._account_links.pop(token, None)

    def create_payment_intent(
        self,
        *,
        amount: int,
        application_fee_amount: int,
        destination: str,
        metadata: dict | None = None,
        currency: str = "usd",
        capture_method: str = "manual",
    ) -> dict[str, Any]:
        with self._lock:
            if destination not in self._contractors:
                raise UnknownAccount(destination)
            if amount <= 0:
                raise ValueError("amount must be positive")
            if application_fee_amount < 0 or application_fee_amount > amount:
                raise ValueError("invalid application_fee_amount")
            if self._client_available < amount:
                raise InsufficientFunds("Insufficient client funds for hold")

            self._client_available -= amount
            self._client_held += amount
            pi_id = _id("pi")
            pi = {
                "id": pi_id,
                "object": "payment_intent",
                "amount": amount,
                "amount_capturable": amount,
                "amount_received": 0,
                "application_fee_amount": application_fee_amount,
                "currency": currency,
                "capture_method": capture_method,
                "status": "requires_capture",
                "client_secret": f"{pi_id}_secret_{secrets.token_hex(8)}",
                "transfer_data": {"destination": destination},
                "metadata": metadata or {},
            }
            self._payment_intents[pi_id] = pi
            return dict(pi)

    def capture_payment_intent(self, pi_id: str) -> dict[str, Any]:
        with self._lock:
            pi = self._payment_intents.get(pi_id)
            if pi is None or pi["status"] != "requires_capture":
                raise InvalidPaymentIntent(pi_id)
            amount = pi["amount"]
            fee = pi["application_fee_amount"]
            dest = pi["transfer_data"]["destination"]
            self._client_held -= amount
            self._platform_available += fee
            self._contractors[dest]["available"] += amount - fee
            pi["status"] = "succeeded"
            pi["amount_capturable"] = 0
            pi["amount_received"] = amount
            return dict(pi)

    def cancel_payment_intent(self, pi_id: str) -> dict[str, Any]:
        with self._lock:
            pi = self._payment_intents.get(pi_id)
            if pi is None or pi["status"] != "requires_capture":
                raise InvalidPaymentIntent(pi_id)
            amount = pi["amount"]
            self._client_held -= amount
            self._client_available += amount
            pi["status"] = "canceled"
            pi["amount_capturable"] = 0
            return dict(pi)

    def get_payment_intent(self, pi_id: str) -> dict[str, Any]:
        with self._lock:
            pi = self._payment_intents.get(pi_id)
            if pi is None:
                raise InvalidPaymentIntent(pi_id)
            return dict(pi)

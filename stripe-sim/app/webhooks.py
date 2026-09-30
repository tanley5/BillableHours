"""Signed Stripe-compatible webhook delivery."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def sign_payload(payload: bytes, secret: str, *, timestamp: int | None = None) -> str:
    ts = int(time.time()) if timestamp is None else timestamp
    signed = f"{ts}.".encode("utf-8") + payload
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def make_event(event_type: str, obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"evt_{uuid.uuid4().hex[:24]}",
        "object": "event",
        "api_version": "2024-11-20.acacia",
        "type": event_type,
        "data": {"object": obj},
        "livemode": False,
        "pending_webhooks": 1,
    }


def deliver_event(
    event: dict[str, Any],
    *,
    webhook_url: str,
    webhook_secret: str,
    timeout: float = 5.0,
) -> None:
    if not webhook_url:
        return
    payload = json.dumps(event, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Stripe-Signature": sign_payload(payload, webhook_secret),
    }
    try:
        httpx.post(webhook_url, content=payload, headers=headers, timeout=timeout)
    except Exception:
        logger.exception("Failed to deliver webhook %s to %s", event.get("type"), webhook_url)

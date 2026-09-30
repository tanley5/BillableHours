"""Stripe-shaped demo companion for BillableHours escrow + Connect."""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.ledger import (
    InsufficientFunds,
    InvalidPaymentIntent,
    LedgerStore,
    UnknownAccount,
)
from app.webhooks import deliver_event, make_event

app = FastAPI(title="BillableHours Stripe Sim", version="0.1.0")
_STORE = LedgerStore()


def get_store() -> LedgerStore:
    return _STORE


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _public_base(request: Request) -> str:
    configured = _env("STRIPE_SIM_PUBLIC_BASE")
    if configured:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")


def _webhook_url() -> str:
    return _env("STRIPE_SIM_WEBHOOK_URL", "")


def _webhook_secret() -> str:
    return _env("STRIPE_WEBHOOK_SECRET", "whsec_sim")


def _emit(event_type: str, obj: dict[str, Any]) -> None:
    deliver_event(
        make_event(event_type, obj),
        webhook_url=_webhook_url(),
        webhook_secret=_webhook_secret(),
    )


def _stripe_error(message: str, *, code: str = "card_declined", err_type: str = "card_error", status: int = 400):
    return JSONResponse(
        status_code=status,
        content={"error": {"type": err_type, "code": code, "message": message}},
    )


def _parse_metadata(form: dict[str, Any]) -> dict[str, str]:
    meta: dict[str, str] = {}
    prefix = "metadata["
    for key, value in form.items():
        if key.startswith(prefix) and key.endswith("]"):
            meta[key[len(prefix) : -1]] = str(value)
    return meta


@app.get("/", response_class=HTMLResponse)
def demo_home() -> str:
    snap = get_store().snapshot()

    def money(cents: int) -> str:
        return f"${cents / 100:,.2f}"

    contractors = snap["contractors"]
    contractor_rows = (
        "".join(
            f"<tr><td><code>{acct}</code></td><td>{money(data['available'])}</td>"
            f"<td>{data.get('email') or '—'}</td></tr>"
            for acct, data in contractors.items()
        )
        or "<tr><td colspan='3'>No contractor accounts yet</td></tr>"
    )
    holds = snap["open_holds"]
    hold_rows = (
        "".join(
            f"<tr><td><code>{h['id']}</code></td><td>{money(h['amount'])}</td>"
            f"<td>{money(h['application_fee_amount'])} fee</td>"
            f"<td><code>{h['destination']}</code></td></tr>"
            for h in holds
        )
        or "<tr><td colspan='4'>No funds on hold</td></tr>"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Stripe Sim — BillableHours</title>
  <style>
    :root {{
      --bg: #f3efe6;
      --ink: #1c1914;
      --muted: #5c564c;
      --line: #d4cdc0;
      --accent: #0f6b5c;
      --card: #fffdf8;
    }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, #e7f2ee 0, transparent 40%),
        linear-gradient(180deg, #f7f2e8, var(--bg));
      color: var(--ink);
      min-height: 100vh;
    }}
    main {{ max-width: 920px; margin: 0 auto; padding: 2.5rem 1.25rem 4rem; }}
    h1 {{ font-size: 1.75rem; margin: 0 0 0.35rem; letter-spacing: -0.02em; }}
    p.lead {{ color: var(--muted); margin: 0 0 1.75rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }}
    @media (max-width: 720px) {{ .grid {{ grid-template-columns: 1fr; }} }}
    .panel {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 1rem 1.1rem;
    }}
    .panel h2 {{ margin: 0 0 0.5rem; font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }}
    .panel .amt {{ font-size: 1.6rem; font-variant-numeric: tabular-nums; }}
    .panel .sub {{ color: var(--muted); font-size: 0.9rem; margin-top: 0.25rem; }}
    section {{ margin-top: 1.75rem; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--card); border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }}
    th, td {{ text-align: left; padding: 0.65rem 0.8rem; border-bottom: 1px solid var(--line); font-size: 0.92rem; }}
    th {{ color: var(--muted); font-weight: 600; }}
    .actions {{ display: flex; gap: 0.75rem; margin-top: 1.25rem; flex-wrap: wrap; }}
    button {{
      background: var(--accent); color: white; border: 0; border-radius: 8px;
      padding: 0.65rem 1rem; font: inherit; cursor: pointer;
    }}
    button.secondary {{ background: transparent; color: var(--accent); border: 1px solid var(--accent); }}
    code {{ font-size: 0.85em; }}
  </style>
</head>
<body>
<main>
  <h1>Stripe Sim</h1>
  <p class="lead">Demo ledgers for BillableHours — Client funds jobs, Platform takes 2%, Contractor receives the rest. Not real Stripe.</p>
  <div class="grid">
    <div class="panel">
      <h2>Client</h2>
      <div class="amt">{money(snap["client"]["available"])}</div>
      <div class="sub">Available · {money(snap["client"]["held"])} on hold</div>
    </div>
    <div class="panel">
      <h2>Platform</h2>
      <div class="amt">{money(snap["platform"]["available"])}</div>
      <div class="sub">Fees captured (2%)</div>
    </div>
    <div class="panel">
      <h2>Contractors</h2>
      <div class="amt">{len(contractors)}</div>
      <div class="sub">Connect accounts</div>
    </div>
  </div>
  <section>
    <h2>Funds on hold</h2>
    <table>
      <thead><tr><th>PaymentIntent</th><th>Amount</th><th>Fee</th><th>Destination</th></tr></thead>
      <tbody>{hold_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Contractor balances</h2>
    <table>
      <thead><tr><th>Account</th><th>Available</th><th>Email</th></tr></thead>
      <tbody>{contractor_rows}</tbody>
    </table>
  </section>
  <div class="actions">
    <form method="post" action="/demo/api/top-up"><input type="hidden" name="amount_cents" value="100000" />
      <button type="submit">Top up client $1,000</button>
    </form>
    <form method="post" action="/demo/api/reset">
      <button class="secondary" type="submit">Reset ledgers</button>
    </form>
  </div>
</main>
</body>
</html>"""


@app.get("/demo/api/ledgers")
def demo_ledgers():
    return get_store().snapshot()


@app.post("/demo/api/reset")
async def demo_reset(request: Request):
    get_store().reset()
    if "text/html" in (request.headers.get("accept") or ""):
        return RedirectResponse("/", status_code=303)
    return {"ok": True, **get_store().snapshot()}


@app.post("/demo/api/top-up")
async def demo_top_up(request: Request):
    amount = 100_000
    ctype = request.headers.get("content-type", "")
    if "application/json" in ctype:
        body = await request.json()
        amount = int(body.get("amount_cents", amount))
    else:
        form = await request.form()
        if "amount_cents" in form:
            amount = int(form["amount_cents"])
    get_store().top_up_client(amount)
    if "application/json" not in ctype and "text/html" in (request.headers.get("accept") or ""):
        return RedirectResponse("/", status_code=303)
    if "application/json" in ctype:
        return {"ok": True, **get_store().snapshot()}
    return RedirectResponse("/", status_code=303)


@app.get("/demo/onboard/{token}")
def demo_onboard(token: str):
    link = get_store().consume_account_link(token)
    if link is None:
        return _stripe_error("Invalid or expired account link", err_type="invalid_request_error", code="resource_missing", status=404)
    account = get_store().get_account(link["account"])
    _emit("account.updated", account)
    return RedirectResponse(link["return_url"], status_code=303)


@app.post("/v1/accounts")
async def create_account(request: Request):
    form = dict(await request.form())
    account = get_store().create_account(
        email=form.get("email") or None,
        metadata=_parse_metadata(form),
        type=form.get("type") or "express",
    )
    _emit("account.updated", account)
    return account


@app.post("/v1/account_links")
async def create_account_link(request: Request):
    form = dict(await request.form())
    account = form.get("account")
    return_url = form.get("return_url")
    refresh_url = form.get("refresh_url") or return_url
    if not account or not return_url:
        return _stripe_error("account and return_url required", err_type="invalid_request_error", code="parameter_missing")
    try:
        link = get_store().create_account_link(
            account=str(account),
            return_url=str(return_url),
            refresh_url=str(refresh_url),
            public_base=_public_base(request),
        )
    except UnknownAccount:
        return _stripe_error("No such account", err_type="invalid_request_error", code="resource_missing", status=404)
    return link


@app.post("/v1/payment_intents")
async def create_payment_intent(request: Request):
    form = dict(await request.form())
    try:
        amount = int(form.get("amount", "0"))
        fee = int(form.get("application_fee_amount", "0"))
        destination = form.get("transfer_data[destination]")
        if not destination:
            return _stripe_error(
                "transfer_data[destination] required",
                err_type="invalid_request_error",
                code="parameter_missing",
            )
        pi = get_store().create_payment_intent(
            amount=amount,
            application_fee_amount=fee,
            destination=str(destination),
            metadata=_parse_metadata(form),
            currency=str(form.get("currency") or "usd"),
            capture_method=str(form.get("capture_method") or "manual"),
        )
    except InsufficientFunds as exc:
        return _stripe_error(str(exc), code="card_declined")
    except UnknownAccount:
        return _stripe_error("No such destination account", err_type="invalid_request_error", code="resource_missing", status=404)
    except ValueError as exc:
        return _stripe_error(str(exc), err_type="invalid_request_error", code="parameter_invalid")
    _emit("payment_intent.amount_capturable_updated", pi)
    return pi


@app.post("/v1/payment_intents/{pi_id}/capture")
def capture_payment_intent(pi_id: str):
    try:
        pi = get_store().capture_payment_intent(pi_id)
    except InvalidPaymentIntent:
        return _stripe_error("PaymentIntent cannot be captured", err_type="invalid_request_error", code="payment_intent_unexpected_state")
    _emit("payment_intent.succeeded", pi)
    return pi


@app.post("/v1/payment_intents/{pi_id}/cancel")
def cancel_payment_intent(pi_id: str):
    try:
        pi = get_store().cancel_payment_intent(pi_id)
    except InvalidPaymentIntent:
        return _stripe_error("PaymentIntent cannot be canceled", err_type="invalid_request_error", code="payment_intent_unexpected_state")
    _emit("payment_intent.canceled", pi)
    return pi


@app.get("/v1/payment_intents/{pi_id}")
def retrieve_payment_intent(pi_id: str):
    try:
        return get_store().get_payment_intent(pi_id)
    except InvalidPaymentIntent:
        return _stripe_error("No such payment_intent", err_type="invalid_request_error", code="resource_missing", status=404)

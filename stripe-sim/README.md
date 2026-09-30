# BillableHours Stripe simulator

Local companion that speaks the Stripe REST subset this app uses (PaymentIntents + Connect Express accounts/links). Demo ledgers only — not real money.

## Demo vs live

| Mode | Env |
|------|-----|
| **Demo (compose)** | `STRIPE_API_BASE=http://stripe-sim:12111`, `STRIPE_SECRET_KEY=sk_test_sim`, `STRIPE_WEBHOOK_SECRET=whsec_sim` |
| **Live** | Unset `STRIPE_API_BASE`; set real Stripe secret + webhook secret |

## Run tests

```bash
cd stripe-sim
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## Demo UI

With compose up: [http://localhost:12111/](http://localhost:12111/) — Client / Platform / Contractor balances, open holds, top-up + reset.

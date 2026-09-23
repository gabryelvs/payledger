# PayLedger

A backend payment platform built around an **immutable double-entry ledger**. Users hold
multi-currency balances and transfer money; every movement is recorded as balanced,
append-only debit/credit entries — the same model real fintech backends (Monzo, Wise,
Revolut) are built on.

Backend only (no UI): the API ships with interactive Swagger docs at `/docs`.

## Hard problems solved

- **Integer money** — all amounts are integer *minor units* (pence/cents) paired with an
  ISO 4217 currency. No floats touch money, so no rounding drift.
- **Double-entry invariant** — each transaction writes ≥2 ledger entries whose signed
  amounts sum to zero; entries are append-only (corrections are new compensating entries).
- **Race-safe transfers** — concurrent transfers on the same wallet are serialised with
  `SELECT ... FOR UPDATE` (wallets locked in id order to avoid deadlocks). No lost updates,
  no overdraw. Proven by a concurrency test that fires 20 parallel transfers.
- **Idempotency** — write endpoints accept an `Idempotency-Key`; a retried request returns
  the original result instead of double-charging.

## Tech stack

Python 3.13 · FastAPI · Pydantic v2 · SQLAlchemy 2 · Alembic · PostgreSQL ·
pytest · ruff · Docker Compose · GitHub Actions.

## Architecture

Layered: **API** (routers + schemas) → **services** (business rules) → **models** (SQLAlchemy)
over PostgreSQL, which is the only datastore: idempotency keys live there too. There is
no rate limiting. See
[docs/architecture.md](docs/architecture.md) for diagrams and the transfer sequence.

## Run locally

```bash
# 1. Start Postgres
docker compose up -d

# 2. Install and run migrations
python -m venv .venv && source .venv/Scripts/activate   # Windows
pip install -e ".[dev]"
alembic upgrade head

# 3. Start the API
uvicorn app.main:app --reload
# open http://localhost:8000/docs
```

## Run the tests

```bash
docker compose up -d        # tests use a real Postgres
pytest                      # ~30 tests incl. the concurrency proof
ruff check .
```

## Example flow

```bash
# Register + log in
curl -X POST localhost:8000/auth/register -H 'content-type: application/json' \
  -d '{"email":"a@b.com","password":"secret123"}'
TOKEN=$(curl -s -X POST localhost:8000/auth/login -H 'content-type: application/json' \
  -d '{"email":"a@b.com","password":"secret123"}' | jq -r .access_token)

# Create two accounts, each with a GBP wallet
A1=$(curl -s -X POST localhost:8000/accounts -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"name":"Main"}' | jq .id)
A2=$(curl -s -X POST localhost:8000/accounts -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"name":"Savings"}' | jq .id)
W1=$(curl -s -X POST localhost:8000/accounts/$A1/wallets -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"currency":"GBP"}' | jq .id)
W2=$(curl -s -X POST localhost:8000/accounts/$A2/wallets -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"currency":"GBP"}' | jq .id)

# Transfer (idempotent) — amounts are minor units, so 500 = £5.00
curl -X POST localhost:8000/transfers -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -H 'Idempotency-Key: demo-1' \
  -d "{\"from_wallet_id\":$W1,\"to_wallet_id\":$W2,\"amount_minor\":500,\"currency\":\"GBP\"}"
```

> Note: real balances are funded from a system *treasury* wallet via `deposit()` — wired
> into tests and available for a future admin endpoint.

## API summary

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/auth/register` | Create user |
| POST | `/auth/login` | Get access + refresh tokens |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/accounts` · GET `/accounts` | Create / list accounts |
| POST · GET | `/accounts/{id}/wallets` | Open / list wallets |
| GET | `/accounts/{id}/wallets/{wid}/statement` | Paginated entry history |
| POST | `/transfers` | Transfer between wallets (idempotent) |
| GET | `/transactions/{id}` | Transaction + its ledger entries |
| GET | `/healthz` | Liveness |

## License

MIT

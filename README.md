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
  Both rules live in the service layer (the balance is checked before every insert, and no
  code path updates or deletes entries); the database itself does not enforce them yet.
- **Race-safe transfers** — concurrent transfers on the same wallet are serialised with
  `SELECT ... FOR UPDATE` (wallets locked in id order to avoid deadlocks). No lost updates,
  no overdraw. Proven by a concurrency test that fires 20 parallel transfers.
- **Idempotency** — `POST /transfers` accepts an `Idempotency-Key` (scoped per user); a
  retried request returns the original result instead of double-charging. The key is
  claimed with `INSERT ... ON CONFLICT DO NOTHING` inside the same database transaction
  as the transfer, so parallel retries cannot both execute. Proven by a test that fires 10
  overlapping requests with one key and checks exactly one transfer happens, with no 500s.
- **Ownership** — a caller can only move money out of, and read, their own wallets and
  transactions: another user's wallet, statement or transaction returns the exact same
  404 body as a missing id. That is not the same as ids being unprobeable in general —
  a transfer's destination can be any wallet (that's what a transfer is), so making one
  reveals whether a destination id exists and whether its currency matches; and
  response timing is not constant-time.

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
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head

# 3. Start the API (the flag is optional: it enables demo deposits, see below)
DEMO_DEPOSITS_ENABLED=true uvicorn app.main:app --reload
# open http://localhost:8000/docs
```

## Run the tests

```bash
docker compose up -d        # tests use a real Postgres
pytest                      # 61 tests, incl. the concurrency proofs
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

# Fund W1 (demo deployments only, see "Demo deposits") — 10000 = £100.00
curl -X POST localhost:8000/accounts/$A1/wallets/$W1/demo-deposit \
  -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"amount_minor":10000}'

# Transfer (idempotent) — amounts are minor units, so 500 = £5.00
curl -X POST localhost:8000/transfers -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -H 'Idempotency-Key: demo-1' \
  -d "{\"from_wallet_id\":$W1,\"to_wallet_id\":$W2,\"amount_minor\":500,\"currency\":\"GBP\"}"
```

## Demo deposits

Money enters the system from a *treasury* wallet via `deposit()`, which writes an ordinary
balanced transaction (treasury debit, wallet credit). So that visitors to the public demo
can try real transfers, `POST /accounts/{id}/wallets/{wid}/demo-deposit` exposes that path
with guard rails:

- **Off by default.** Enabled only when the environment sets `DEMO_DEPOSITS_ENABLED=true`;
  otherwise it returns `403 DEMO_DEPOSITS_DISABLED`. The public demo sets it; a
  production deployment would not.
- **Own wallets only.** Anyone else's wallet gets `404 WALLET_NOT_FOUND`.
- **Capped** at 100000 minor units (1,000.00) per call (`422 DEMO_DEPOSIT_LIMIT_EXCEEDED`).

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | local compose Postgres | SQLAlchemy URL (`postgresql+psycopg://...`) |
| `JWT_SECRET` | `change-me-in-prod` | HMAC key for access/refresh tokens: set a long random value in any deployment |
| `ACCESS_TTL_MIN` | `15` | Access token lifetime (minutes) |
| `REFRESH_TTL_DAYS` | `7` | Refresh token lifetime (days) |
| `DEMO_DEPOSITS_ENABLED` | `false` | Enables the demo deposit endpoint (see above) |

## Deploy

The API deploys as a [Vercel Function](https://vercel.com/docs/functions/runtimes/python)
(FastAPI on Python) backed by [Neon](https://neon.tech) serverless Postgres — both on
free tiers. Vercel auto-detects the `app` instance in `app/main.py` and installs
dependencies from `pyproject.toml`; `vercel.json` pins the function's region to `lhr1`
(London) and excludes `tests/`, `migrations/` and `docs/` from its bundle, and
`.python-version` pins the runtime to Python 3.13 (Vercel defaults to 3.12 otherwise).
The Hobby plan caps a function at 10 seconds and a 500 MB bundle.

**Environment variables** — set these in the Vercel project's dashboard, not in any
committed file:

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | Neon's pooled connection string (the `-pooler` host), e.g. `postgresql://user:pass@ep-xxx-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require` |
| `JWT_SECRET` | a long random value |
| `DEMO_DEPOSITS_ENABLED` | `true`, for the public demo |

A `postgres://` or `postgresql://` URL is rewritten to `postgresql+psycopg://`
automatically (see `app/config.py`), so Neon's connection string works as-is. On Vercel
the app also opens the database with `NullPool` and `prepare_threshold=None` instead of
its normal local pool (see `app/db/session.py`): each function invocation gets its own
short-lived connection through Neon's PgBouncer pooler, and disabling psycopg3's
server-side prepared statements avoids errors under PgBouncer's transaction-mode
pooling. Neon also suspends compute when idle, so an invocation's first query after a
quiet spell can be slower while it wakes back up.

**Migrations run separately** — Vercel has no release-phase hook, so apply them by hand
*before* traffic depends on the new schema, against Neon's **direct** (non-pooler)
connection string:

```bash
DATABASE_URL='postgresql+psycopg://user:pass@ep-xxx.eu-west-2.aws.neon.tech/neondb?sslmode=require' \
  alembic upgrade head
```

**Live demo:** https://payledger-gv.vercel.app/docs — the Vercel project is named
`payledger-gv`; this URL only resolves once that project exists and has been deployed.

## API summary

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/auth/register` | Create user |
| POST | `/auth/login` | Get access + refresh tokens |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/accounts` · GET `/accounts` | Create / list accounts |
| POST · GET | `/accounts/{id}/wallets` | Open / list wallets |
| GET | `/accounts/{id}/wallets/{wid}/statement` | Paginated entry history |
| POST | `/accounts/{id}/wallets/{wid}/demo-deposit` | Demo only: fund your own wallet (off by default) |
| POST | `/transfers` | Transfer between wallets (idempotent) |
| GET | `/transactions/{id}` | Transaction + its ledger entries |
| GET | `/healthz` | Liveness |

## License

[MIT](LICENSE)

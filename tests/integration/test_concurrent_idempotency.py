import threading
import time

from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.db.session import SessionLocal, engine
from app.main import app
from app.models.ledger import Transaction
from app.models.wallet import Wallet
from app.services.transfer_service import deposit

# Server errors must come back as 500 responses, not exceptions in worker threads.
client = TestClient(app, raise_server_exceptions=False)

N = 10
KEY = "same-key-under-load"


def _setup():
    client.post("/auth/register", json={"email": "idem@x.com", "password": "secret123"})
    tok = client.post(
        "/auth/login", json={"email": "idem@x.com", "password": "secret123"}
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    a1 = client.post("/accounts", json={"name": "Main"}, headers=h).json()["id"]
    a2 = client.post("/accounts", json={"name": "Savings"}, headers=h).json()["id"]
    w1 = client.post(f"/accounts/{a1}/wallets", json={"currency": "GBP"}, headers=h)
    w2 = client.post(f"/accounts/{a2}/wallets", json={"currency": "GBP"}, headers=h)
    return h, w1.json()["id"], w2.json()["id"]


def _wait_until_blocked(n: int, timeout: float = 10.0) -> None:
    """Wait until n backends are parked on a row/transaction lock."""
    deadline = time.monotonic() + timeout
    waiting = 0
    while time.monotonic() < deadline:
        with engine.connect() as c:  # fresh transaction = fresh pg_stat snapshot
            waiting = c.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND wait_event_type = 'Lock'"
                )
            ).scalar_one()
        if waiting >= n:
            return
        time.sleep(0.02)
    raise AssertionError(f"only {waiting}/{n} requests blocked")


def test_parallel_retries_with_one_key_transfer_exactly_once():
    """N identical requests (same Idempotency-Key) in flight at once: one transfer, no 500s.

    Thread timing alone rarely overlaps the requests, so the test holds the source
    wallet's row lock while they arrive. Every request is then parked mid-flight at
    the same moment, which is exactly the window a lookup-then-insert scheme loses.
    """
    h, src, dst = _setup()
    with SessionLocal() as s:
        deposit(s, src, 10_000, "GBP")  # funds for all N, so only idempotency can stop them

    payload = {"from_wallet_id": src, "to_wallet_id": dst, "amount_minor": 100, "currency": "GBP"}
    headers = {"Idempotency-Key": KEY, **h}
    responses = []
    lock = threading.Lock()

    def worker():
        r = client.post("/transfers", json=payload, headers=headers)
        with lock:
            responses.append(r)

    with SessionLocal() as holder:
        holder.execute(select(Wallet).where(Wallet.id == src).with_for_update())
        threads = [threading.Thread(target=worker) for _ in range(N)]
        for t in threads:
            t.start()
        _wait_until_blocked(N)
        holder.rollback()  # release: let them race
    for t in threads:
        t.join()

    statuses = sorted(r.status_code for r in responses)
    assert len(responses) == N
    assert 500 not in statuses, statuses
    assert set(statuses) <= {201, 409}, statuses
    # Every success is the same transfer replayed, never a new one.
    assert len({r.json()["transaction_id"] for r in responses if r.status_code == 201}) == 1

    with SessionLocal() as s:
        executed = s.execute(
            select(func.count()).select_from(Transaction).where(Transaction.idempotency_key == KEY)
        ).scalar_one()
        assert executed == 1
        assert s.get(Wallet, src).balance_minor == 9_900
        assert s.get(Wallet, dst).balance_minor == 100

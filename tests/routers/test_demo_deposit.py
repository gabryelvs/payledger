"""POST /accounts/{account_id}/wallets/{wallet_id}/demo-deposit

Lets a demo user fund their OWN wallet from the treasury, through the normal
double-entry path, when DEMO_DEPOSITS_ENABLED is on. Off by default.
"""

import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import Settings, settings
from app.db.session import SessionLocal
from app.main import app
from app.models.account import Account
from app.models.ledger import LedgerEntry
from app.models.wallet import Wallet
from app.services.demo_deposits import DEMO_DEPOSIT_MAX_MINOR
from app.services.transfer_service import TREASURY_ACCOUNT_NAME

client = TestClient(app)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "demo_deposits_enabled", True)


def _user(email: str) -> dict:
    client.post("/auth/register", json={"email": email, "password": "secret123"})
    tok = client.post(
        "/auth/login", json={"email": email, "password": "secret123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _wallet(h: dict) -> tuple[int, int]:
    acc = client.post("/accounts", json={"name": "Main"}, headers=h).json()["id"]
    wal = client.post(
        f"/accounts/{acc}/wallets", json={"currency": "GBP"}, headers=h
    ).json()["id"]
    return acc, wal


def _deposit(h: dict, acc: int, wal: int, amount: int):
    return client.post(
        f"/accounts/{acc}/wallets/{wal}/demo-deposit",
        json={"amount_minor": amount},
        headers=h,
    )


def _balance(wallet_id: int) -> int:
    with SessionLocal() as s:
        return s.get(Wallet, wallet_id).balance_minor


def test_demo_deposits_are_off_unless_configured(monkeypatch):
    monkeypatch.delenv("DEMO_DEPOSITS_ENABLED", raising=False)
    assert Settings(_env_file=None).demo_deposits_enabled is False
    monkeypatch.setenv("DEMO_DEPOSITS_ENABLED", "true")
    assert Settings(_env_file=None).demo_deposits_enabled is True


def test_disabled_endpoint_refuses_and_moves_nothing(monkeypatch):
    monkeypatch.setattr(settings, "demo_deposits_enabled", False)
    h = _user("demo@x.com")
    acc, wal = _wallet(h)

    r = _deposit(h, acc, wal, 500)

    assert r.status_code == 403
    assert r.json()["error"]["code"] == "DEMO_DEPOSITS_DISABLED"
    assert _balance(wal) == 0


def test_credits_the_callers_own_wallet(enabled):
    h = _user("demo@x.com")
    acc, wal = _wallet(h)

    r = _deposit(h, acc, wal, 50_000)

    assert r.status_code == 201
    body = r.json()
    assert body["balance_minor"] == 50_000
    assert body["status"] == "completed"
    assert _balance(wal) == 50_000
    # ...and the funds are spendable through the normal transfer path.
    _, other = _wallet(h)
    t = client.post(
        "/transfers",
        json={"from_wallet_id": wal, "to_wallet_id": other, "amount_minor": 500, "currency": "GBP"},
        headers=h,
    )
    assert t.status_code == 201
    assert _balance(other) == 500


def test_ledger_stays_balanced(enabled):
    h = _user("demo@x.com")
    acc, wal = _wallet(h)

    txn_id = _deposit(h, acc, wal, 12_345).json()["transaction_id"]

    with SessionLocal() as s:
        entries = s.execute(
            select(LedgerEntry).where(LedgerEntry.transaction_id == txn_id)
        ).scalars().all()
        # One debit on the treasury, one credit on the wallet, summing to zero.
        assert sorted(e.amount_minor for e in entries) == [-12_345, 12_345]
        assert {e.wallet_id for e in entries if e.amount_minor > 0} == {wal}
        assert s.execute(select(func.sum(LedgerEntry.amount_minor))).scalar_one() == 0
        # The cached balance agrees with the wallet's ledger history.
        ledger_total = s.execute(
            select(func.sum(LedgerEntry.amount_minor)).where(LedgerEntry.wallet_id == wal)
        ).scalar_one()
        assert ledger_total == s.get(Wallet, wal).balance_minor == 12_345


def test_rejected_for_a_wallet_the_caller_does_not_own(enabled):
    ha, hb = _user("alice@x.com"), _user("bob@x.com")
    acc_a, wal_a = _wallet(ha)
    acc_b, _ = _wallet(hb)

    via_their_account = _deposit(hb, acc_a, wal_a, 500)
    via_own_account = _deposit(hb, acc_b, wal_a, 500)

    for r in (via_their_account, via_own_account):
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "WALLET_NOT_FOUND"
    assert _balance(wal_a) == 0


def test_rejected_over_the_per_call_cap(enabled):
    h = _user("demo@x.com")
    acc, wal = _wallet(h)

    over = _deposit(h, acc, wal, DEMO_DEPOSIT_MAX_MINOR + 1)

    assert over.status_code == 422
    assert over.json()["error"]["code"] == "DEMO_DEPOSIT_LIMIT_EXCEEDED"
    assert _balance(wal) == 0
    assert _deposit(h, acc, wal, DEMO_DEPOSIT_MAX_MINOR).status_code == 201


def test_cap_is_one_thousand_units():
    assert DEMO_DEPOSIT_MAX_MINOR == 100_000  # 1,000.00 in minor units


@pytest.mark.parametrize("amount", [0, -100])
def test_rejects_non_positive_amounts(enabled, amount):
    h = _user("demo@x.com")
    acc, wal = _wallet(h)

    assert _deposit(h, acc, wal, amount).status_code == 422
    assert _balance(wal) == 0


def test_concurrent_first_ever_deposits_all_succeed(enabled):
    """20 different users' very first deposit, at once.

    Nothing has ever deposited before, so the system user, the treasury account and
    the treasury wallet all still need to be created -- and all 20 requests race to
    create them. On a fresh schema this used to give a unique violation on the system
    user's email (creating it twice), surfaced as a 500 to the caller, on most of the
    20 requests.
    """
    client = TestClient(app, raise_server_exceptions=False)
    wallets = []
    for i in range(20):
        h = _user(f"race{i}@x.com")
        acc, wal = _wallet(h)
        wallets.append((h, acc, wal))

    responses: list = [None] * 20
    lock = threading.Lock()

    def worker(i, h, acc, wal):
        r = client.post(
            f"/accounts/{acc}/wallets/{wal}/demo-deposit",
            json={"amount_minor": 1_000},
            headers=h,
        )
        with lock:
            responses[i] = r

    threads = [
        threading.Thread(target=worker, args=(i, *w)) for i, w in enumerate(wallets)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    statuses = [r.status_code if r is not None else None for r in responses]
    assert statuses == [201] * 20, statuses

    with SessionLocal() as s:
        for _, _, wal in wallets:
            assert s.get(Wallet, wal).balance_minor == 1_000
        # money is conserved: every ledger entry, across every transaction, sums to 0
        assert s.execute(select(func.sum(LedgerEntry.amount_minor))).scalar_one() == 0
        # exactly one treasury account was created despite the race
        treasury_accounts = s.execute(
            select(func.count())
            .select_from(Account)
            .where(Account.name == TREASURY_ACCOUNT_NAME)
        ).scalar_one()
        assert treasury_accounts == 1

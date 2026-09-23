"""A caller may only move money out of, and read, what they own.

Non-owned resources must be indistinguishable from missing ones (404, same body),
so the API does not leak which ids exist.
"""

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.wallet import Wallet
from app.services.transfer_service import deposit

client = TestClient(app)

MISSING_ID = 999_999


def _user(email: str) -> dict:
    client.post("/auth/register", json={"email": email, "password": "secret123"})
    tok = client.post(
        "/auth/login", json={"email": email, "password": "secret123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _account_with_wallet(h: dict, name: str = "Main") -> tuple[int, int]:
    acc = client.post("/accounts", json={"name": name}, headers=h).json()["id"]
    wal = client.post(
        f"/accounts/{acc}/wallets", json={"currency": "GBP"}, headers=h
    ).json()["id"]
    return acc, wal


def _fund(wallet_id: int, amount: int = 1000) -> None:
    with SessionLocal() as s:
        deposit(s, wallet_id, amount, "GBP")


def _balance(wallet_id: int) -> int:
    with SessionLocal() as s:
        return s.get(Wallet, wallet_id).balance_minor


def _transfer(h: dict, src: int, dst: int, amount: int = 100):
    return client.post(
        "/transfers",
        json={
            "from_wallet_id": src,
            "to_wallet_id": dst,
            "amount_minor": amount,
            "currency": "GBP",
        },
        headers=h,
    )


def _two_users():
    ha, hb = _user("alice@x.com"), _user("bob@x.com")
    acc_a, wal_a = _account_with_wallet(ha)
    acc_b, wal_b = _account_with_wallet(hb)
    _fund(wal_a)
    return ha, hb, acc_a, wal_a, acc_b, wal_b


# --- transfers -----------------------------------------------------------------


def test_cannot_transfer_from_another_users_wallet():
    _, hb, _, wal_a, _, wal_b = _two_users()

    r = _transfer(hb, wal_a, wal_b)

    assert r.status_code == 404
    assert r.json()["error"]["code"] == "WALLET_NOT_FOUND"
    assert _balance(wal_a) == 1000
    assert _balance(wal_b) == 0


def test_non_owned_source_wallet_looks_the_same_as_a_missing_one():
    _, hb, _, wal_a, _, wal_b = _two_users()

    not_owned = _transfer(hb, wal_a, wal_b)
    missing = _transfer(hb, MISSING_ID, wal_b)

    assert not_owned.status_code == missing.status_code == 404
    assert not_owned.json() == missing.json()


def test_owner_can_transfer_to_another_users_wallet():
    ha, _, _, wal_a, _, wal_b = _two_users()

    r = _transfer(ha, wal_a, wal_b, 250)

    assert r.status_code == 201
    assert _balance(wal_a) == 750
    assert _balance(wal_b) == 250


# --- wallets -------------------------------------------------------------------


def test_cannot_list_another_users_wallets():
    ha, hb, acc_a, wal_a, _, _ = _two_users()

    r = client.get(f"/accounts/{acc_a}/wallets", headers=hb)
    missing = client.get(f"/accounts/{MISSING_ID}/wallets", headers=hb)

    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"
    assert r.json() == missing.json()
    owner = client.get(f"/accounts/{acc_a}/wallets", headers=ha)
    assert owner.status_code == 200
    assert [w["id"] for w in owner.json()] == [wal_a]


def test_cannot_open_wallet_on_another_users_account():
    ha, hb, acc_a, _, _, _ = _two_users()

    r = client.post(f"/accounts/{acc_a}/wallets", json={"currency": "USD"}, headers=hb)

    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"
    owner = client.get(f"/accounts/{acc_a}/wallets", headers=ha).json()
    assert [w["currency"] for w in owner] == ["GBP"]


def test_cannot_read_another_users_statement():
    ha, hb, acc_a, wal_a, acc_b, _ = _two_users()

    via_their_account = client.get(
        f"/accounts/{acc_a}/wallets/{wal_a}/statement", headers=hb
    )
    via_own_account = client.get(
        f"/accounts/{acc_b}/wallets/{wal_a}/statement", headers=hb
    )

    assert via_their_account.status_code == 404
    assert via_own_account.status_code == 404
    assert via_own_account.json()["error"]["code"] == "WALLET_NOT_FOUND"
    owner = client.get(f"/accounts/{acc_a}/wallets/{wal_a}/statement", headers=ha)
    assert owner.status_code == 200
    assert [e["amount_minor"] for e in owner.json()] == [1000]


# --- transactions --------------------------------------------------------------


def test_cannot_read_another_users_transaction():
    ha, hb, _, wal_a, _, _ = _two_users()
    _, wal_a2 = _account_with_wallet(ha, "Savings")
    txn_id = _transfer(ha, wal_a, wal_a2).json()["transaction_id"]

    r = client.get(f"/transactions/{txn_id}", headers=hb)
    missing = client.get(f"/transactions/{MISSING_ID}", headers=hb)

    assert r.status_code == 404
    assert r.json()["error"]["code"] == "TRANSACTION_NOT_FOUND"
    assert r.json() == missing.json()
    owner = client.get(f"/transactions/{txn_id}", headers=ha)
    assert owner.status_code == 200
    assert owner.json()["id"] == txn_id


def test_counterparty_can_read_a_transfer_into_their_wallet():
    ha, hb, _, wal_a, _, wal_b = _two_users()
    txn_id = _transfer(ha, wal_a, wal_b).json()["transaction_id"]

    r = client.get(f"/transactions/{txn_id}", headers=hb)

    assert r.status_code == 200
    assert {e["wallet_id"] for e in r.json()["entries"]} == {wal_a, wal_b}

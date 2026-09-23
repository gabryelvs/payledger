from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _setup(email="tr@x.com"):
    client.post("/auth/register", json={"email": email, "password": "secret123"})
    tok = client.post(
        "/auth/login", json={"email": email, "password": "secret123"}
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    a1 = client.post("/accounts", json={"name": "Main"}, headers=h).json()["id"]
    a2 = client.post("/accounts", json={"name": "Savings"}, headers=h).json()["id"]
    w1 = client.post(
        f"/accounts/{a1}/wallets", json={"currency": "GBP"}, headers=h
    ).json()["id"]
    w2 = client.post(
        f"/accounts/{a2}/wallets", json={"currency": "GBP"}, headers=h
    ).json()["id"]
    return h, w1, w2


def test_transfer_insufficient_returns_422():
    h, w1, w2 = _setup()
    r = client.post(
        "/transfers",
        json={
            "from_wallet_id": w1,
            "to_wallet_id": w2,
            "amount_minor": 100,
            "currency": "GBP",
        },
        headers=h,
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INSUFFICIENT_FUNDS"


def test_idempotent_replay_same_transaction():
    from app.db.session import SessionLocal
    from app.services.transfer_service import deposit

    h, w1, w2 = _setup()
    with SessionLocal() as s:
        deposit(s, w1, 1000, "GBP")
    payload = {
        "from_wallet_id": w1,
        "to_wallet_id": w2,
        "amount_minor": 200,
        "currency": "GBP",
    }
    k = {"Idempotency-Key": "abc-123", **h}
    r1 = client.post("/transfers", json=payload, headers=k)
    r2 = client.post("/transfers", json=payload, headers=k)
    assert r1.status_code == 201
    assert r1.json() == r2.json()


def _fund(wallet_id, amount=1000):
    from app.db.session import SessionLocal
    from app.services.transfer_service import deposit

    with SessionLocal() as s:
        deposit(s, wallet_id, amount, "GBP")


def _balance(wallet_id):
    from app.db.session import SessionLocal
    from app.models.wallet import Wallet

    with SessionLocal() as s:
        return s.get(Wallet, wallet_id).balance_minor


def _payload(src, dst, amount=200):
    return {"from_wallet_id": src, "to_wallet_id": dst, "amount_minor": amount, "currency": "GBP"}


def test_idempotent_replay_moves_money_once():
    h, w1, w2 = _setup()
    _fund(w1)
    k = {"Idempotency-Key": "once", **h}
    client.post("/transfers", json=_payload(w1, w2), headers=k)
    client.post("/transfers", json=_payload(w1, w2), headers=k)
    assert _balance(w1) == 800
    assert _balance(w2) == 200


def test_same_key_different_body_returns_409():
    h, w1, w2 = _setup()
    _fund(w1)
    k = {"Idempotency-Key": "reused", **h}
    assert client.post("/transfers", json=_payload(w1, w2, 200), headers=k).status_code == 201
    r = client.post("/transfers", json=_payload(w1, w2, 300), headers=k)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert _balance(w1) == 800


def test_idempotency_keys_are_scoped_per_user():
    ha, a1, a2 = _setup("alice@x.com")
    hb, b1, b2 = _setup("bob@x.com")
    _fund(a1)
    _fund(b1)
    ra = client.post("/transfers", json=_payload(a1, a2), headers={"Idempotency-Key": "k", **ha})
    rb = client.post("/transfers", json=_payload(b1, b2), headers={"Idempotency-Key": "k", **hb})
    assert ra.status_code == rb.status_code == 201
    assert ra.json()["transaction_id"] != rb.json()["transaction_id"]
    assert _balance(a1) == _balance(b1) == 800


def test_failed_transfer_does_not_consume_the_key():
    h, w1, w2 = _setup()
    k = {"Idempotency-Key": "retry-after-funding", **h}
    first = client.post("/transfers", json=_payload(w1, w2), headers=k)
    assert first.json()["error"]["code"] == "INSUFFICIENT_FUNDS"
    _fund(w1)
    assert client.post("/transfers", json=_payload(w1, w2), headers=k).status_code == 201
    assert _balance(w2) == 200

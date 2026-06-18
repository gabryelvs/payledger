from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _setup():
    client.post("/auth/register", json={"email": "tr@x.com", "password": "secret123"})
    tok = client.post(
        "/auth/login", json={"email": "tr@x.com", "password": "secret123"}
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


from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_register_endpoint_returns_201():
    r = client.post("/auth/register", json={"email": "x@y.com", "password": "secret123"})
    assert r.status_code == 201
    assert r.json()["email"] == "x@y.com"


def test_treasury_system_address_cannot_be_registered():
    # The treasury is owned by system@payledger; nobody may sign up as that user.
    r = client.post(
        "/auth/register", json={"email": "system@payledger", "password": "secret123"}
    )
    assert r.status_code == 422

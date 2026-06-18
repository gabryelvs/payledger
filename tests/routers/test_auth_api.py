from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_register_endpoint_returns_201():
    r = client.post("/auth/register", json={"email": "x@y.com", "password": "secret123"})
    assert r.status_code == 201
    assert r.json()["email"] == "x@y.com"

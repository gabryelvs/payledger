from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _token(email):
    client.post("/auth/register", json={"email": email, "password": "secret123"})
    return client.post(
        "/auth/login", json={"email": email, "password": "secret123"}
    ).json()["access_token"]


def test_create_account_requires_auth_and_works():
    assert client.post("/accounts", json={"name": "Main"}).status_code == 401
    h = {"Authorization": f"Bearer {_token('a1@x.com')}"}
    r = client.post("/accounts", json={"name": "Main"}, headers=h)
    assert r.status_code == 201

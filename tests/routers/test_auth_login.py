from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_login_returns_token_pair():
    client.post("/auth/register", json={"email": "l@m.com", "password": "secret123"})
    r = client.post("/auth/login", json={"email": "l@m.com", "password": "secret123"})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["refresh_token"]


def test_refresh_returns_new_pair():
    client.post("/auth/register", json={"email": "r@m.com", "password": "secret123"})
    tokens = client.post(
        "/auth/login", json={"email": "r@m.com", "password": "secret123"}
    ).json()
    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_bad_password_401():
    client.post("/auth/register", json={"email": "b@m.com", "password": "secret123"})
    r = client.post("/auth/login", json={"email": "b@m.com", "password": "wrongpass"})
    assert r.status_code == 401

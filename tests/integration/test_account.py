import pytest
from fastapi.testclient import TestClient
from test_auth_flows import NEW_PASSWORD, PASSWORD

from rag.api.deps import limiter
from rag.api.main import app
from rag.config.settings import settings

HEADERS = {"X-API-Key": settings.RAG_API_KEY}


@pytest.fixture(autouse=True)
def _no_rate_limits(monkeypatch):
    monkeypatch.setattr(limiter, "enabled", False)


def _login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_sessions_list_and_revoke(verified_login):
    first = TestClient(app)
    email = verified_login(first)
    second = TestClient(app)
    assert _login(second, email, PASSWORD).status_code == 200

    listing = first.get("/account/sessions", headers=HEADERS).json()
    assert len(listing) == 2
    assert sum(1 for s in listing if s["current"]) == 1
    other = next(s for s in listing if not s["current"])

    own = next(s for s in listing if s["current"])
    assert first.delete(f"/account/sessions/{own['id']}", headers=HEADERS).status_code == 400

    assert first.delete(f"/account/sessions/{other['id']}", headers=HEADERS).status_code == 200
    assert second.get("/documents", headers=HEADERS).status_code == 401
    assert first.get("/documents", headers=HEADERS).status_code == 200


def test_revoke_other_sessions(verified_login):
    first = TestClient(app)
    email = verified_login(first)
    second = TestClient(app)
    assert _login(second, email, PASSWORD).status_code == 200

    assert first.post("/account/sessions/revoke-others", headers=HEADERS).status_code == 200
    assert second.get("/documents", headers=HEADERS).status_code == 401
    assert first.get("/documents", headers=HEADERS).status_code == 200


def test_change_password(verified_login):
    first = TestClient(app)
    email = verified_login(first)
    second = TestClient(app)
    assert _login(second, email, PASSWORD).status_code == 200

    wrong = first.post(
        "/account/password",
        json={"current_password": "not-the-password", "new_password": NEW_PASSWORD},
        headers=HEADERS,
    )
    assert wrong.status_code == 400

    ok = first.post(
        "/account/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=HEADERS,
    )
    assert ok.status_code == 200, ok.text

    assert first.get("/documents", headers=HEADERS).status_code == 200  # this device stays in
    assert second.get("/documents", headers=HEADERS).status_code == 401  # others are signed out
    assert _login(TestClient(app), email, PASSWORD).status_code == 401
    assert _login(TestClient(app), email, NEW_PASSWORD).status_code == 200


def test_delete_account_removes_the_user_and_their_data(verified_login):
    client = TestClient(app)
    email = verified_login(client)
    created = client.post("/conversations", json={"title": "temp"}, headers=HEADERS)
    assert created.status_code == 200, created.text

    refused = client.post(
        "/account/delete",
        json={"confirm_email": "someone@else.com", "password": PASSWORD},
        headers=HEADERS,
    )
    assert refused.status_code == 422

    bad_password = client.post(
        "/account/delete",
        json={"confirm_email": email, "password": "wrong-password"},
        headers=HEADERS,
    )
    assert bad_password.status_code == 400

    deleted = client.post(
        "/account/delete", json={"confirm_email": email, "password": PASSWORD}, headers=HEADERS
    )
    assert deleted.status_code == 200, deleted.text
    assert _login(TestClient(app), email, PASSWORD).status_code == 401

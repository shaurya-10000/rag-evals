import time
import uuid
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from rag.api.main import app
from rag.config.settings import settings

PASSWORD = "testpassword123"
NEW_PASSWORD = "a-brand-new-password-456"
HEADERS = {"X-API-Key": settings.RAG_API_KEY}


def _login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


# ------------------------------------------------------------------ email verification


def test_login_blocked_until_email_verified(register):
    client = TestClient(app)
    email = register(client)

    # Signup does not log you in.
    assert "access_token" not in client.cookies

    wrong = _login(client, email, "not-the-password")
    assert wrong.status_code == 401

    blocked = _login(client, email, PASSWORD)
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "email_not_verified"
    assert "access_token" not in client.cookies


def test_verify_email_enables_login_and_token_is_single_use(register, sent_emails):
    client = TestClient(app)
    email = register(client)
    token = sent_emails["verify"][email]

    assert client.post("/auth/verify-email", json={"token": token}).status_code == 200
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 400
    assert client.post("/auth/verify-email", json={"token": "garbage"}).status_code == 400

    assert _login(client, email, PASSWORD).status_code == 200


def test_forgot_and_resend_do_not_reveal_unknown_emails(sent_emails):
    client = TestClient(app)
    ghost = f"ghost_{uuid.uuid4().hex[:8]}@example.com"

    for path in ("/auth/forgot-password", "/auth/resend-verification"):
        response = client.post(path, json={"email": ghost})
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    assert ghost not in sent_emails["reset"]
    assert ghost not in sent_emails["verify"]


# ------------------------------------------------------------------ password reset


def test_password_reset_flow(register, sent_emails):
    client = TestClient(app)
    email = register(client)  # never verified: resetting proves inbox access

    assert client.post("/auth/forgot-password", json={"email": email}).status_code == 200
    token = sent_emails["reset"][email]

    # A too-short password is rejected without burning the link.
    short = client.post("/auth/reset-password", json={"token": token, "password": "short"})
    assert short.status_code == 422

    ok = client.post("/auth/reset-password", json={"token": token, "password": NEW_PASSWORD})
    assert ok.status_code == 200, ok.text

    reuse = client.post("/auth/reset-password", json={"token": token, "password": NEW_PASSWORD})
    assert reuse.status_code == 400

    assert _login(client, email, PASSWORD).status_code == 401
    assert _login(client, email, NEW_PASSWORD).status_code == 200


def test_password_reset_invalidates_existing_sessions(verified_login, sent_emails):
    client = TestClient(app)
    email = verified_login(client)
    assert client.get("/documents", headers=HEADERS).status_code == 200

    client.post("/auth/forgot-password", json={"email": email})
    token = sent_emails["reset"][email]

    # JWT issue times are whole seconds, so make sure the reset lands in a later second.
    time.sleep(1.1)
    reset = client.post("/auth/reset-password", json={"token": token, "password": NEW_PASSWORD})
    assert reset.status_code == 200, reset.text

    # The cookie from before the reset must no longer work.
    assert client.get("/documents", headers=HEADERS).status_code == 401


# ------------------------------------------------------------------ Google OAuth


def _fake_google(monkeypatch, **overrides):
    uniq = uuid.uuid4().hex[:8]
    profile = {
        "sub": f"sub-{uniq}",
        "email": f"google_{uniq}@example.com",
        "email_verified": True,
        "name": "Google Tester",
    }
    profile.update(overrides)
    monkeypatch.setattr("rag.auth.google.fetch_profile", lambda code: profile)
    return profile


def _google_callback(client, state="abc", cookie_state="abc"):
    client.cookies.set("oauth_state", cookie_state)
    return client.get(
        "/auth/google/callback",
        params={"code": "fake-code", "state": state},
        follow_redirects=False,
    )


def _one_time_code(response) -> str:
    assert response.status_code in (302, 307), response.text
    query = parse_qs(urlparse(response.headers["location"]).query)
    return query["code"][0]


def test_google_callback_creates_verified_user(monkeypatch):
    client = TestClient(app)
    profile = _fake_google(monkeypatch)

    code = _one_time_code(_google_callback(client))

    exchange = client.post("/auth/oauth/exchange", json={"code": code})
    assert exchange.status_code == 200, exchange.text
    assert exchange.json()["email"] == profile["email"]
    assert client.get("/documents", headers=HEADERS).status_code == 200

    # The one-time code cannot be replayed.
    replay = client.post("/auth/oauth/exchange", json={"code": code})
    assert replay.status_code == 400


def test_google_callback_rejects_state_mismatch(monkeypatch):
    client = TestClient(app)
    _fake_google(monkeypatch)

    response = _google_callback(client, state="from-google", cookie_state="from-cookie")
    assert response.status_code in (302, 307)
    assert "error=google_failed" in response.headers["location"]


def test_google_callback_rejects_unverified_google_email(monkeypatch):
    client = TestClient(app)
    _fake_google(monkeypatch, email_verified=False)

    response = _google_callback(client)
    assert response.status_code in (302, 307)
    assert "error=google_unverified" in response.headers["location"]


def test_google_login_drops_password_of_preregistered_unverified_account(monkeypatch, register):
    client = TestClient(app)
    email = register(client)  # someone signed up with this address but never verified it
    _fake_google(monkeypatch, email=email)

    code = _one_time_code(_google_callback(client))
    assert client.post("/auth/oauth/exchange", json={"code": code}).status_code == 200

    # The password chosen at pre-registration must no longer work.
    other = TestClient(app)
    response = _login(other, email, PASSWORD)
    assert response.status_code == 400
    assert "Google" in response.json()["detail"]

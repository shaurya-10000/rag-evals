import uuid

import pytest

from rag.api.deps import limiter

PASSWORD = "testpassword123"


@pytest.fixture(autouse=True)
def _no_rate_limits(monkeypatch):
    """Tests share one client IP, so keep them from tripping each other's limits."""
    monkeypatch.setattr(limiter, "enabled", False)


@pytest.fixture(autouse=True)
def sent_emails(monkeypatch) -> dict[str, dict[str, str]]:
    """Capture outgoing emails (email -> token) so tests never send real ones."""
    sent: dict[str, dict[str, str]] = {"verify": {}, "reset": {}}

    def fake_verify(to: str, username: str, token: str) -> None:
        sent["verify"][to] = token

    def fake_reset(to: str, username: str, token: str) -> None:
        sent["reset"][to] = token

    monkeypatch.setattr("rag.api.auth.send_verification_email", fake_verify)
    monkeypatch.setattr("rag.api.auth.send_password_reset_email", fake_reset)
    return sent


@pytest.fixture
def register():
    """Register a fresh unverified user and return their email."""

    def _register(client, email=None) -> str:
        uniq = uuid.uuid4().hex[:8]
        email = email or f"test_{uniq}@example.com"
        response = client.post(
            "/auth/register",
            json={"email": email, "username": f"testuser_{uniq}", "password": PASSWORD},
        )
        assert response.status_code == 200, response.text
        return email

    return _register


@pytest.fixture
def verified_login(register, sent_emails):
    """Register, verify through the emailed token, log in, and return the email."""

    def _verified_login(client) -> str:
        email = register(client)
        verify = client.post("/auth/verify-email", json={"token": sent_emails["verify"][email]})
        assert verify.status_code == 200, verify.text
        login = client.post("/auth/login", json={"email": email, "password": PASSWORD})
        assert login.status_code == 200, login.text
        return email

    return _verified_login

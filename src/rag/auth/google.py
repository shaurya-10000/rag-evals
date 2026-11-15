from typing import Any
from urllib.parse import urlencode

import httpx

from rag.config.settings import settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def is_configured() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def redirect_uri() -> str:
    return f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}/auth/google/callback"


def build_auth_url(state: str) -> str:
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def fetch_profile(code: str) -> dict[str, Any]:
    """Exchange the authorization code and return Google's userinfo for that user."""
    token_res = httpx.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=10.0,
    )
    token_res.raise_for_status()
    access_token = token_res.json()["access_token"]

    info_res = httpx.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10.0,
    )
    info_res.raise_for_status()
    profile: dict[str, Any] = info_res.json()
    return profile

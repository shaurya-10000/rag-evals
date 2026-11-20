import logging
import re
import secrets
from datetime import UTC, datetime
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from rag.api.deps import limiter
from rag.auth import google, sessions, tokens
from rag.auth.utils import create_access_token, get_password_hash, verify_password
from rag.config.settings import settings
from rag.db import get_db
from rag.db_models import OAuthAccount, User
from rag.mailer import send_password_reset_email, send_verification_email

logger = logging.getLogger("rag.api.auth")
router = APIRouter(prefix="/auth", tags=["auth"])

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
VERIFY_TTL_MINUTES = 60 * 24
RESET_TTL_MINUTES = 30
OAUTH_CODE_TTL_MINUTES = 2
EMAIL_COOLDOWN_SECONDS = 60
OAUTH_STATE_COOKIE = "oauth_state"
OAUTH_STATE_PATH = "/auth/google"


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class EmailRequest(BaseModel):
    email: EmailStr


class TokenRequest(BaseModel):
    token: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


class CodeRequest(BaseModel):
    code: str


def _set_token_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.JWT_EXPIRES_MINUTES * 60,
    )


def _start_session(db: Session, request: Request, response: Response, user: User) -> None:
    """Record this login as a revocable session and set the cookie that carries its id."""
    session = sessions.create_session(
        db, user.id, sessions.client_user_agent(request), sessions.client_ip(request)
    )
    _set_token_cookie(response, create_access_token(user.id, user.email, session.id))


def _find_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(func.lower(User.email) == email.lower()).first()


def _check_password_length(password: str) -> None:
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Password must be {PASSWORD_MIN_LENGTH}-{PASSWORD_MAX_LENGTH} characters",
        )


def _queue_verification_email(db: Session, user: User, background_tasks: BackgroundTasks) -> None:
    raw = tokens.create_token(db, user.id, tokens.VERIFY_EMAIL, VERIFY_TTL_MINUTES)
    background_tasks.add_task(send_verification_email, user.email, user.username, raw)


def _frontend_url(path: str, **params: str) -> str:
    base = f"{settings.FRONTEND_URL.rstrip('/')}{path}"
    return f"{base}?{urlencode(params)}" if params else base


# ------------------------------------------------------------------ email + password


@router.post("/register")
@limiter.limit("10/minute")
def register(
    request: Request,
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    _check_password_length(payload.password)
    email = payload.email.lower()

    if _find_user_by_email(db, email):
        raise HTTPException(status_code=400, detail="Email already registered")

    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        email=email,
        username=payload.username,
        hashed_password=get_password_hash(payload.password),
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # No session yet: the user has to verify their email first.
    _queue_verification_email(db, user, background_tasks)
    return {"status": "verification_sent", "email": user.email, "username": user.username}


@router.post("/login")
@limiter.limit("10/minute")
def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    user = _find_user_by_email(db, payload.email)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.hashed_password is None:
        raise HTTPException(
            status_code=400,
            detail="This account uses Google sign-in. Continue with Google, "
            "or use Forgot password to set a password.",
        )

    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.email_verified:
        raise HTTPException(status_code=403, detail="email_not_verified")

    _start_session(db, request, response, user)
    return {"status": "logged_in", "email": user.email, "username": user.username}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    sessions.revoke_from_request(db, request)
    response.delete_cookie("access_token")
    return {"status": "logged_out"}


@router.post("/verify-email")
@limiter.limit("20/minute")
def verify_email(
    request: Request,
    payload: TokenRequest,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    user_id = tokens.consume_token(db, payload.token, tokens.VERIFY_EMAIL)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=400, detail="This verification link is invalid or expired.")
    user.email_verified = True
    db.commit()
    return {"status": "verified"}


@router.post("/resend-verification")
@limiter.limit("5/minute")
def resend_verification(
    request: Request,
    payload: EmailRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    user = _find_user_by_email(db, payload.email)
    if (
        user
        and not user.email_verified
        and not tokens.issued_within(db, user.id, tokens.VERIFY_EMAIL, EMAIL_COOLDOWN_SECONDS)
    ):
        _queue_verification_email(db, user, background_tasks)
    # Same answer whether or not the account exists.
    return {"status": "ok"}


@router.post("/forgot-password")
@limiter.limit("5/minute")
def forgot_password(
    request: Request,
    payload: EmailRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    user = _find_user_by_email(db, payload.email)
    if user and not tokens.issued_within(
        db, user.id, tokens.RESET_PASSWORD, EMAIL_COOLDOWN_SECONDS
    ):
        raw = tokens.create_token(db, user.id, tokens.RESET_PASSWORD, RESET_TTL_MINUTES)
        background_tasks.add_task(send_password_reset_email, user.email, user.username, raw)
    return {"status": "ok"}


@router.post("/reset-password")
@limiter.limit("10/minute")
def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    # Validate first so a too-short password does not burn the link.
    _check_password_length(payload.password)

    user_id = tokens.consume_token(db, payload.token, tokens.RESET_PASSWORD)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=400, detail="This reset link is invalid or expired.")

    user.hashed_password = get_password_hash(payload.password)
    user.password_changed_at = datetime.now(UTC)
    # Receiving the reset email proves control of the inbox.
    user.email_verified = True
    db.commit()
    return {"status": "password_reset"}


# ------------------------------------------------------------------ Google OAuth


def _unique_username(db: Session, seed: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_]", "", seed.replace(" ", "_"))[:40] or "user"
    if len(base) < 3:
        base = f"{base}user"
    candidate = base
    while db.query(User).filter(User.username == candidate).first():
        candidate = f"{base}{secrets.randbelow(9000) + 1000}"
    return candidate


def _get_or_create_google_user(db: Session, sub: str, email: str, name: str) -> User:
    link = (
        db.query(OAuthAccount)
        .filter(OAuthAccount.provider == "google", OAuthAccount.provider_user_id == sub)
        .first()
    )
    if link:
        existing = db.get(User, link.user_id)
        if existing is not None:
            return existing

    user = _find_user_by_email(db, email)
    if user is None:
        user = User(
            email=email,
            username=_unique_username(db, name or email.split("@")[0]),
            hashed_password=None,
            email_verified=True,
        )
        db.add(user)
        db.flush()
    elif not user.email_verified:
        # Someone may have pre-registered this address with a password they chose.
        # Google just proved the real owner, so drop that password.
        user.hashed_password = None
        user.email_verified = True

    db.add(OAuthAccount(user_id=user.id, provider="google", provider_user_id=sub, email=email))
    db.commit()
    db.refresh(user)
    return user


@router.get("/google/login")
@limiter.limit("20/minute")
def google_login(request: Request) -> RedirectResponse:
    if not google.is_configured():
        return RedirectResponse(_frontend_url("/sign-in", error="google_unavailable"))

    state = secrets.token_urlsafe(24)
    response = RedirectResponse(google.build_auth_url(state))
    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=state,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=600,
        path=OAUTH_STATE_PATH,
    )
    return response


@router.get("/google/callback")
@limiter.limit("20/minute")
def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),  # noqa: B008
) -> RedirectResponse:
    def finish(url: str) -> RedirectResponse:
        redirect = RedirectResponse(url)
        redirect.delete_cookie(OAUTH_STATE_COOKIE, path=OAUTH_STATE_PATH)
        return redirect

    expected = request.cookies.get(OAUTH_STATE_COOKIE)
    if (
        error
        or not code
        or not state
        or not expected
        or not secrets.compare_digest(state.encode(), expected.encode())
    ):
        return finish(_frontend_url("/sign-in", error="google_failed"))

    try:
        profile = google.fetch_profile(code)
    except (httpx.HTTPError, KeyError, ValueError):
        logger.exception("Google token exchange failed")
        return finish(_frontend_url("/sign-in", error="google_failed"))

    sub = profile.get("sub")
    email = profile.get("email")
    if not sub or not email or profile.get("email_verified") not in (True, "true"):
        return finish(_frontend_url("/sign-in", error="google_unverified"))

    user = _get_or_create_google_user(
        db, str(sub), str(email).lower(), str(profile.get("name", ""))
    )

    # The session cookie has to live on the frontend's domain, so hand the browser a
    # short-lived one-time code and let the Next.js server exchange it for the cookie.
    raw = tokens.create_token(db, user.id, tokens.OAUTH_LOGIN, OAUTH_CODE_TTL_MINUTES)
    return finish(_frontend_url("/api/auth/google/callback", code=raw))


@router.post("/oauth/exchange")
@limiter.limit("20/minute")
def oauth_exchange(
    request: Request,
    payload: CodeRequest,
    response: Response,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    user_id = tokens.consume_token(db, payload.code, tokens.OAUTH_LOGIN)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=400, detail="Sign-in expired. Please try again.")
    _start_session(db, request, response, user)
    return {"status": "logged_in", "email": user.email, "username": user.username}

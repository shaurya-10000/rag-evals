import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from rag.db_models import AuthToken

VERIFY_EMAIL = "verify_email"
RESET_PASSWORD = "reset_password"
OAUTH_LOGIN = "oauth_login"


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_token(db: Session, user_id: uuid.UUID, purpose: str, ttl_minutes: int) -> str:
    """Create a single-use token and return the raw value. Older unused ones are revoked."""
    db.execute(
        delete(AuthToken).where(
            AuthToken.user_id == user_id,
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
        )
    )
    raw = secrets.token_urlsafe(32)
    db.add(
        AuthToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=_hash(raw),
            expires_at=datetime.now(UTC) + timedelta(minutes=ttl_minutes),
        )
    )
    db.commit()
    return raw


def consume_token(db: Session, raw: str, purpose: str) -> uuid.UUID | None:
    """Mark a token used and return its user id, or None if invalid, used or expired."""
    token = (
        db.query(AuthToken)
        .filter(AuthToken.token_hash == _hash(raw), AuthToken.purpose == purpose)
        .with_for_update()
        .first()
    )
    now = datetime.now(UTC)
    if token is None or token.used_at is not None or token.expires_at < now:
        return None
    user_id = token.user_id
    token.used_at = now
    db.commit()
    return user_id


def issued_within(db: Session, user_id: uuid.UUID, purpose: str, seconds: int) -> bool:
    cutoff = datetime.now(UTC) - timedelta(seconds=seconds)
    row = (
        db.query(AuthToken.id)
        .filter(
            AuthToken.user_id == user_id,
            AuthToken.purpose == purpose,
            AuthToken.created_at > cutoff,
        )
        .first()
    )
    return row is not None

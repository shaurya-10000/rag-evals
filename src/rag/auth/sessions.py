"""Server-side login sessions: lets users see their devices and sign any of them out."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Request
from jose import JWTError, jwt
from sqlalchemy import DateTime, ForeignKey, String, delete, select, update
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from rag.config.settings import settings
from rag.db_models import Base

COOKIE_NAME = "access_token"
TOUCH_AFTER = timedelta(minutes=5)
KEEP_EXPIRED = timedelta(days=7)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)


def _now() -> datetime:
    return datetime.now(UTC)


def _parse(raw: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(raw))
    except ValueError:
        return None


def client_user_agent(request: Request) -> str | None:
    value = request.headers.get("x-client-user-agent") or request.headers.get("user-agent")
    return value[:300] if value else None


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded[:64]
    return request.client.host[:64] if request.client else None


def describe_device(user_agent: str | None) -> str:
    if not user_agent:
        return "Unknown device"
    ua = user_agent.lower()
    browsers = (
        ("edg/", "Edge"),
        ("opr/", "Opera"),
        ("firefox/", "Firefox"),
        ("chrome/", "Chrome"),
        ("safari/", "Safari"),
    )
    systems = (
        ("windows", "Windows"),
        ("iphone", "iPhone"),
        ("ipad", "iPad"),
        ("android", "Android"),
        ("mac os", "macOS"),
        ("linux", "Linux"),
    )
    browser = next((name for key, name in browsers if key in ua), "Browser")
    system = next((name for key, name in systems if key in ua), "unknown system")
    return f"{browser} on {system}"


def create_session(
    db: Session, user_id: uuid.UUID, user_agent: str | None, ip: str | None
) -> UserSession:
    now = _now()
    db.execute(
        delete(UserSession).where(
            UserSession.user_id == user_id, UserSession.expires_at < now - KEEP_EXPIRED
        )
    )
    row = UserSession(
        user_id=user_id,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(minutes=settings.JWT_EXPIRES_MINUTES),
        user_agent=user_agent,
        ip_address=ip,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def touch_if_active(db: Session, user_id: uuid.UUID, raw_session_id: object) -> bool:
    """True if the session exists, belongs to the user and is neither revoked nor expired."""
    session_id = _parse(raw_session_id)
    if session_id is None:
        return False
    row = db.get(UserSession, session_id)
    now = _now()
    if row is None or row.user_id != user_id or row.revoked_at is not None or row.expires_at <= now:
        return False
    if now - row.last_seen_at > TOUCH_AFTER:
        row.last_seen_at = now
        db.commit()
    return True


def list_active(db: Session, user_id: uuid.UUID) -> list[UserSession]:
    stmt = (
        select(UserSession)
        .where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > _now(),
        )
        .order_by(UserSession.last_seen_at.desc())
    )
    return list(db.execute(stmt).scalars())


def revoke(db: Session, user_id: uuid.UUID, session_id: uuid.UUID) -> bool:
    row = db.get(UserSession, session_id)
    if row is None or row.user_id != user_id or row.revoked_at is not None:
        return False
    row.revoked_at = _now()
    db.commit()
    return True


def revoke_all(db: Session, user_id: uuid.UUID, except_id: uuid.UUID | None = None) -> None:
    stmt = update(UserSession).where(
        UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
    )
    if except_id is not None:
        stmt = stmt.where(UserSession.id != except_id)
    db.execute(stmt.values(revoked_at=_now()))
    db.commit()


def revoke_from_request(db: Session, request: Request) -> None:
    """Best effort: end the session named by the request's cookie (used by logout)."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": False},
        )
    except JWTError:
        return
    session_id = _parse(payload.get("sid"))
    user_id = _parse(payload.get("sub"))
    if session_id is not None and user_id is not None:
        revoke(db, user_id, session_id)

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from rag.config.settings import settings
from rag.db import get_db
from rag.db_models import User

password_hash = PasswordHash.recommended()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def create_access_token(user_id: uuid.UUID, email: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=settings.JWT_EXPIRES_MINUTES),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return str(token)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),  # noqa: B008
) -> User:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token") from None

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Email not verified")

    # A password reset invalidates every session issued before it.
    if user.password_changed_at is not None:
        issued_at = payload.get("iat")
        if not isinstance(issued_at, int) or issued_at < int(user.password_changed_at.timestamp()):
            raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    return user

import uuid
from datetime import UTC, datetime, timedelta

from jose import jwt
from pwdlib import PasswordHash

from rag.config.settings import settings

password_hash = PasswordHash.recommended()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def create_access_token(user_id: uuid.UUID, email: str) -> str:
    expires = datetime.now(UTC) + timedelta(minutes=settings.JWT_EXPIRES_MINUTES)
    payload = {"sub": str(user_id), "email": email, "exp": expires}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)  # type: ignore[no-any-return]


def decode_token(token: str) -> dict[str, str]:
    return jwt.decode(  # type: ignore[no-any-return]
        token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
    )

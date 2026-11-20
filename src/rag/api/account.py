import logging
import uuid
from datetime import UTC, datetime
from datetime import datetime as DateTime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from rag.api.auth import _check_password_length, _start_session
from rag.api.deps import limiter, verify_api_key
from rag.auth import sessions
from rag.auth.sessions import UserSession
from rag.auth.utils import get_current_user, get_password_hash, verify_password
from rag.db import get_db
from rag.db_models import (
    AuthToken,
    Chunk,
    Collection,
    Conversation,
    Document,
    IngestJob,
    Message,
    OAuthAccount,
    SharedChat,
    User,
)

logger = logging.getLogger("rag.api.account")
router = APIRouter(prefix="/account", tags=["account"])


class AccountOut(BaseModel):
    email: str
    username: str
    has_password: bool
    google_linked: bool


class SessionOut(BaseModel):
    id: uuid.UUID
    device: str
    created_at: DateTime
    last_seen_at: DateTime
    current: bool


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class DeleteAccountRequest(BaseModel):
    confirm_email: str
    password: str | None = None


def _current_session_id(request: Request) -> uuid.UUID | None:
    raw = getattr(request.state, "session_id", None)
    try:
        return uuid.UUID(str(raw)) if raw else None
    except ValueError:
        return None


@router.get("", response_model=AccountOut)
def get_account(
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> AccountOut:
    linked = db.scalar(
        select(func.count())
        .select_from(OAuthAccount)
        .where(OAuthAccount.user_id == current_user.id)
    )
    return AccountOut(
        email=current_user.email,
        username=current_user.username,
        has_password=current_user.hashed_password is not None,
        google_linked=bool(linked),
    )


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> list[SessionOut]:
    current_id = _current_session_id(request)
    return [
        SessionOut(
            id=row.id,
            device=sessions.describe_device(row.user_agent),
            created_at=row.created_at,
            last_seen_at=row.last_seen_at,
            current=row.id == current_id,
        )
        for row in sessions.list_active(db, current_user.id)
    ]


@router.post("/sessions/revoke-others")
@limiter.limit("10/minute")
def revoke_other_sessions(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    sessions.revoke_all(db, current_user.id, except_id=_current_session_id(request))
    logger.info("Signed out other sessions", extra={"fields": {"user_id": str(current_user.id)}})
    return {"status": "ok"}


@router.delete("/sessions/{session_id}")
@limiter.limit("20/minute")
def revoke_session(
    request: Request,
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    if session_id == _current_session_id(request):
        raise HTTPException(status_code=400, detail="Use Sign out to end this device's session.")
    if not sessions.revoke(db, current_user.id, session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "revoked"}


@router.post("/password")
@limiter.limit("5/minute")
def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    response: Response,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    if current_user.hashed_password is None:
        raise HTTPException(
            status_code=400,
            detail="This account has no password yet. Use Forgot password to set one.",
        )
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    _check_password_length(payload.new_password)
    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=422, detail="Choose a password you have not used just now.")

    current_user.hashed_password = get_password_hash(payload.new_password)
    # Invalidates every token issued before this moment, on every device.
    current_user.password_changed_at = datetime.now(UTC)
    db.commit()
    sessions.revoke_all(db, current_user.id)
    # Keep this device signed in with a fresh session.
    _start_session(db, request, response, current_user)
    logger.info("Password changed", extra={"fields": {"user_id": str(current_user.id)}})
    return {"status": "password_changed"}


def _purge_user(db: Session, user: User) -> None:
    """Delete the user and everything they own, children first."""
    uid = user.id
    doc_ids = select(Document.id).where(Document.user_id == uid)
    conversation_ids = select(Conversation.id).where(Conversation.user_id == uid)
    db.execute(delete(Chunk).where(Chunk.document_id.in_(doc_ids)))
    db.execute(delete(Message).where(Message.conversation_id.in_(conversation_ids)))
    owned: tuple[Any, ...] = (
        SharedChat,
        IngestJob,
        Document,
        Collection,
        Conversation,
        OAuthAccount,
        AuthToken,
        UserSession,
    )
    for model in owned:
        db.execute(delete(model).where(model.user_id == uid))
    db.execute(delete(User).where(User.id == uid))
    db.commit()


@router.post("/delete")
@limiter.limit("3/minute")
def delete_account(
    request: Request,
    payload: DeleteAccountRequest,
    response: Response,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    if payload.confirm_email.strip().lower() != current_user.email.lower():
        raise HTTPException(status_code=422, detail="Type your email address to confirm.")
    if current_user.hashed_password is not None and (
        not payload.password or not verify_password(payload.password, current_user.hashed_password)
    ):
        raise HTTPException(status_code=400, detail="Password is incorrect.")

    user_id = str(current_user.id)
    try:
        _purge_user(db, current_user)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Account deletion failed", extra={"fields": {"user_id": user_id}})
        raise HTTPException(
            status_code=500, detail="Could not delete the account. Please try again."
        ) from None
    response.delete_cookie("access_token")
    logger.info("Account deleted", extra={"fields": {"user_id": user_id}})
    return {"status": "deleted"}

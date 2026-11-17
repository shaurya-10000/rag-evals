import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from rag.api.deps import limiter, verify_api_key
from rag.api.schemas import SharedChatOut, SharedMessage, SharedSource, ShareOut
from rag.auth.utils import get_current_user
from rag.chat_repository import ConversationRepository
from rag.db import get_db
from rag.db_models import SharedChat, User
from rag.share_repository import ShareRepository

logger = logging.getLogger("rag.api.shares")
router = APIRouter(tags=["shares"])


def _share_out(share: SharedChat | None) -> ShareOut:
    if share is None:
        return ShareOut(shared=False)
    return ShareOut(
        shared=True, token=share.token, created_at=share.created_at, updated_at=share.updated_at
    )


def _conversation_or_404(db: Session, user: User, conversation_id: uuid.UUID):  # type: ignore[no-untyped-def]
    conversation = ConversationRepository(db).get(user.id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.get("/conversations/{conversation_id}/share", response_model=ShareOut)
def get_share(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> ShareOut:
    _conversation_or_404(db, current_user, conversation_id)
    return _share_out(ShareRepository(db).get_for_conversation(current_user.id, conversation_id))


@router.post("/conversations/{conversation_id}/share", response_model=ShareOut)
@limiter.limit("20/minute")
def create_or_update_share(
    request: Request,
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> ShareOut:
    conversation = _conversation_or_404(db, current_user, conversation_id)
    if not conversation.messages:
        raise HTTPException(status_code=422, detail="There is nothing to share yet.")
    share = ShareRepository(db).upsert(current_user.id, conversation)
    logger.info("Share link saved conversation=%s user=%s", conversation_id, current_user.username)
    return _share_out(share)


@router.delete("/conversations/{conversation_id}/share", response_model=ShareOut)
def stop_sharing(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> ShareOut:
    _conversation_or_404(db, current_user, conversation_id)
    repo = ShareRepository(db)
    share = repo.get_for_conversation(current_user.id, conversation_id)
    if share is not None:
        repo.delete(share)
    return ShareOut(shared=False)


@router.get("/shared/{token}", response_model=SharedChatOut)
@limiter.limit("60/minute")
def read_shared_chat(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> SharedChatOut:
    """Public read: no user session, but only the web app (which holds the API key) calls it."""
    share = ShareRepository(db).get_by_token(token)
    if share is None:
        raise HTTPException(status_code=404, detail="This shared chat does not exist.")
    return SharedChatOut(
        title=share.title,
        shared_at=share.updated_at,
        messages=[
            SharedMessage(
                role=str(item["role"]),
                content=str(item["content"]),
                sources=[SharedSource(**source) for source in item.get("sources", [])],
            )
            for item in share.snapshot
        ],
    )

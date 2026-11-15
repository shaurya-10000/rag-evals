import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from rag.api.deps import limiter, verify_api_key
from rag.api.schemas import (
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    ConversationUpdate,
    ImportRequest,
    ImportResponse,
    MessageOut,
)
from rag.auth.utils import get_current_user
from rag.chat_repository import ConversationRepository, ImportedConversation, ImportedMessage
from rag.db import get_db
from rag.db_models import Conversation, Message, User

logger = logging.getLogger("rag.api.conversations")
router = APIRouter()


def _conversation_out(conversation: Conversation) -> ConversationOut:
    return ConversationOut(
        id=conversation.id,
        title=conversation.title,
        pinned=conversation.pinned,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _message_out(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        sources=list(message.sources or []),
        created_at=message.created_at,
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Conversation not found")


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> list[ConversationOut]:
    repo = ConversationRepository(db)
    return [_conversation_out(c) for c in repo.list_for_user(current_user.id)]


@router.post("/conversations", response_model=ConversationOut)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> ConversationOut:
    repo = ConversationRepository(db)
    return _conversation_out(repo.create(current_user.id, payload.title))


# Declared before /conversations/{id} so the static path is matched first.
@router.post("/conversations/import", response_model=ImportResponse)
@limiter.limit("5/minute")
def import_conversations(
    request: Request,
    payload: ImportRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> ImportResponse:
    items = [
        ImportedConversation(
            title=conv.title,
            pinned=conv.pinned,
            created_at=_aware(conv.created_at),
            messages=[
                ImportedMessage(role=m.role, content=m.content, sources=m.sources)
                for m in conv.messages
            ],
        )
        for conv in payload.conversations
    ]
    repo = ConversationRepository(db)
    imported = repo.import_conversations(current_user.id, items)
    logger.info("Imported %d legacy conversations for user=%s", imported, current_user.username)
    return ImportResponse(imported=imported)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> ConversationDetail:
    repo = ConversationRepository(db)
    conversation = repo.get(current_user.id, conversation_id)
    if conversation is None:
        raise _not_found()
    return ConversationDetail(
        **_conversation_out(conversation).model_dump(),
        messages=[_message_out(m) for m in conversation.messages],
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> ConversationOut:
    if payload.title is None and payload.pinned is None:
        raise HTTPException(status_code=422, detail="Nothing to update")
    title = payload.title.strip() if payload.title is not None else None
    if title is not None and not title:
        raise HTTPException(status_code=422, detail="Title cannot be empty")

    repo = ConversationRepository(db)
    conversation = repo.get(current_user.id, conversation_id)
    if conversation is None:
        raise _not_found()
    return _conversation_out(repo.update(conversation, title, payload.pinned))


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    repo = ConversationRepository(db)
    conversation = repo.get(current_user.id, conversation_id)
    if conversation is None:
        raise _not_found()
    repo.delete(conversation)
    return {"status": "deleted"}

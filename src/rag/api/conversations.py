import logging
import uuid
from datetime import UTC, datetime
from typing import Any

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
from rag.db_models import Chunk, Conversation, Document, Message, User

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


def _as_uuid(value: object) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _resolve_documents(
    db: Session, user_id: uuid.UUID, messages: list[Message]
) -> tuple[dict[uuid.UUID, uuid.UUID], dict[uuid.UUID, str]]:
    """Look up live document info for saved citations. Always scoped to the current user.

    Returns (chunk_id -> document_id for old citations that lack a document id,
    document_id -> current title for every document that still exists).
    """
    chunk_ids: set[uuid.UUID] = set()
    doc_ids: set[uuid.UUID] = set()
    for message in messages:
        for source in message.sources or []:
            known_doc = _as_uuid(source.get("document_id"))
            if known_doc is not None:
                doc_ids.add(known_doc)
                continue
            legacy_chunk = _as_uuid(source.get("id"))
            if legacy_chunk is not None:
                chunk_ids.add(legacy_chunk)

    chunk_to_doc: dict[uuid.UUID, uuid.UUID] = {}
    if chunk_ids:
        chunk_rows = (
            db.query(Chunk.id, Chunk.document_id)
            .join(Document, Document.id == Chunk.document_id)
            .filter(Chunk.id.in_(chunk_ids), Document.user_id == user_id)
            .all()
        )
        chunk_to_doc = {row[0]: row[1] for row in chunk_rows}
        doc_ids.update(chunk_to_doc.values())

    titles: dict[uuid.UUID, str] = {}
    if doc_ids:
        doc_rows = (
            db.query(Document.id, Document.title)
            .filter(Document.id.in_(doc_ids), Document.user_id == user_id)
            .all()
        )
        titles = {row[0]: row[1] for row in doc_rows}
    return chunk_to_doc, titles


def _enrich_source(
    source: dict[str, Any],
    chunk_to_doc: dict[uuid.UUID, uuid.UUID],
    titles: dict[uuid.UUID, str],
) -> dict[str, Any]:
    enriched = dict(source)
    doc_id = _as_uuid(source.get("document_id"))
    if doc_id is None:
        chunk_id = _as_uuid(source.get("id"))
        if chunk_id is not None:
            doc_id = chunk_to_doc.get(chunk_id)

    title = titles.get(doc_id) if doc_id is not None else None
    enriched["document_id"] = str(doc_id) if doc_id is not None else None
    enriched["document_available"] = title is not None
    if title is not None:
        enriched["document_title"] = title
    return enriched


def _message_out(
    message: Message,
    chunk_to_doc: dict[uuid.UUID, uuid.UUID],
    titles: dict[uuid.UUID, str],
) -> MessageOut:
    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        sources=[_enrich_source(s, chunk_to_doc, titles) for s in (message.sources or [])],
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
    messages = list(conversation.messages)
    chunk_to_doc, titles = _resolve_documents(db, current_user.id, messages)
    return ConversationDetail(
        **_conversation_out(conversation).model_dump(),
        messages=[_message_out(m, chunk_to_doc, titles) for m in messages],
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

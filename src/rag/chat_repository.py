import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from rag.db_models import Conversation, Message

DEFAULT_TITLE = "New Chat"
MAX_TITLE_CHARS = 255
LIST_LIMIT = 200


def _clean_title(title: str | None) -> str:
    cleaned = (title or "").strip()[:MAX_TITLE_CHARS]
    return cleaned or DEFAULT_TITLE


@dataclass(frozen=True)
class ImportedMessage:
    role: str
    content: str
    sources: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ImportedConversation:
    title: str
    pinned: bool
    created_at: datetime
    messages: list[ImportedMessage]


class ConversationRepository:
    """Per-user chat history. Every lookup is scoped by user_id."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_user(self, user_id: uuid.UUID, limit: int = LIST_LIMIT) -> list[Conversation]:
        return (
            self.db.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .all()
        )

    def get(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation | None:
        return (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .first()
        )

    def create(self, user_id: uuid.UUID, title: str | None = None) -> Conversation:
        conversation = Conversation(user_id=user_id, title=_clean_title(title))
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def update(
        self, conversation: Conversation, title: str | None, pinned: bool | None
    ) -> Conversation:
        if title is not None:
            conversation.title = _clean_title(title)
        if pinned is not None:
            conversation.pinned = pinned
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def delete(self, conversation: Conversation) -> None:
        self.db.delete(conversation)
        self.db.commit()

    def add_message(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        sources: list[dict[str, Any]] | None = None,
    ) -> Message:
        now = datetime.now(UTC)
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            sources=sources or [],
            created_at=now,
        )
        self.db.add(message)
        self.db.query(Conversation).filter(Conversation.id == conversation_id).update(
            {"updated_at": now}, synchronize_session=False
        )
        self.db.commit()
        return message

    def import_conversations(self, user_id: uuid.UUID, items: list[ImportedConversation]) -> int:
        """Bulk-create conversations (used once to migrate LocalStorage history)."""
        try:
            for item in items:
                conversation = Conversation(
                    user_id=user_id,
                    title=_clean_title(item.title),
                    pinned=item.pinned,
                    created_at=item.created_at,
                    updated_at=item.created_at,
                )
                self.db.add(conversation)
                self.db.flush()
                for offset, message in enumerate(item.messages):
                    self.db.add(
                        Message(
                            conversation_id=conversation.id,
                            role=message.role,
                            content=message.content,
                            sources=message.sources,
                            created_at=item.created_at + timedelta(milliseconds=offset),
                        )
                    )
                conversation.updated_at = item.created_at + timedelta(
                    milliseconds=len(item.messages)
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return len(items)

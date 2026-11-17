import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from rag.db_models import Conversation, Message

DEFAULT_TITLE = "New Chat"
MAX_TITLE_CHARS = 255
LIST_LIMIT = 200
SEARCH_LIMIT = 20
SEARCH_SCAN_LIMIT = 300
MAX_SEARCH_CHARS = 100
SNIPPET_RADIUS = 60


def _clean_title(title: str | None) -> str:
    cleaned = (title or "").strip()[:MAX_TITLE_CHARS]
    return cleaned or DEFAULT_TITLE


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def make_snippet(text: str, needle: str) -> str:
    """A short excerpt of `text` around the first match of `needle`."""
    index = text.lower().find(needle.lower())
    if index < 0:
        return " ".join(text.split())[: SNIPPET_RADIUS * 2]
    start = max(0, index - SNIPPET_RADIUS)
    end = min(len(text), index + len(needle) + SNIPPET_RADIUS)
    excerpt = " ".join(text[start:end].split())
    return f"{'...' if start > 0 else ''}{excerpt}{'...' if end < len(text) else ''}"


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


@dataclass(frozen=True)
class SearchHit:
    conversation: Conversation
    snippet: str | None


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
        *,
        rewritten_query: str | None = None,
        refused: bool = False,
        message_id: uuid.UUID | None = None,
    ) -> Message:
        now = datetime.now(UTC)
        message = Message(
            id=message_id or uuid.uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            sources=sources or [],
            rewritten_query=rewritten_query,
            refused=refused,
            created_at=now,
        )
        self.db.add(message)
        self.db.query(Conversation).filter(Conversation.id == conversation_id).update(
            {"updated_at": now}, synchronize_session=False
        )
        self.db.commit()
        return message

    def get_message(
        self, user_id: uuid.UUID, conversation_id: uuid.UUID, message_id: uuid.UUID
    ) -> Message | None:
        return (
            self.db.query(Message)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .filter(
                Message.id == message_id,
                Message.conversation_id == conversation_id,
                Conversation.user_id == user_id,
            )
            .first()
        )

    def set_feedback(self, message: Message, rating: int | None, comment: str | None) -> Message:
        message.feedback = rating
        message.feedback_comment = comment if rating is not None else None
        self.db.commit()
        self.db.refresh(message)
        return message

    def search(self, user_id: uuid.UUID, query: str, limit: int = SEARCH_LIMIT) -> list[SearchHit]:
        """Chats whose title or any message contains `query` (case-insensitive)."""
        needle = query.strip()[:MAX_SEARCH_CHARS]
        if not needle:
            return []
        pattern = f"%{_escape_like(needle)}%"

        found: dict[uuid.UUID, Conversation] = {
            c.id: c
            for c in self.db.query(Conversation)
            .filter(Conversation.user_id == user_id, Conversation.title.ilike(pattern, escape="\\"))
            .all()
        }

        message_rows = (
            self.db.query(Message.conversation_id, Message.content)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .filter(Conversation.user_id == user_id, Message.content.ilike(pattern, escape="\\"))
            .order_by(Message.created_at.desc())
            .limit(SEARCH_SCAN_LIMIT)
            .all()
        )
        snippets: dict[uuid.UUID, str] = {}
        for conversation_id, content in message_rows:
            snippets.setdefault(conversation_id, make_snippet(content, needle))

        missing = [cid for cid in snippets if cid not in found]
        if missing:
            rows = (
                self.db.query(Conversation)
                .filter(Conversation.user_id == user_id, Conversation.id.in_(missing))
                .all()
            )
            found.update({c.id: c for c in rows})

        hits = [SearchHit(c, snippets.get(c.id)) for c in found.values()]
        hits.sort(key=lambda hit: hit.conversation.updated_at, reverse=True)
        return hits[:limit]

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

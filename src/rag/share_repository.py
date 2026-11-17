import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from rag.db_models import Conversation, Message, SharedChat

TOKEN_BYTES = 32
MAX_TOKEN_CHARS = 64
MAX_SNAPSHOT_MESSAGES = 500


def build_snapshot(messages: list[Message]) -> list[dict[str, Any]]:
    """What a share link may show. Internal ids and metadata never leave the system."""
    return [
        {
            "role": message.role,
            "content": message.content,
            "sources": [
                {
                    "document_title": source.get("document_title"),
                    "content": str(source.get("content", "")),
                }
                for source in (message.sources or [])
            ],
        }
        for message in messages[-MAX_SNAPSHOT_MESSAGES:]
    ]


class ShareRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_conversation(
        self, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> SharedChat | None:
        return (
            self.db.query(SharedChat)
            .filter(SharedChat.user_id == user_id, SharedChat.conversation_id == conversation_id)
            .first()
        )

    def get_by_token(self, token: str) -> SharedChat | None:
        if not token or len(token) > MAX_TOKEN_CHARS:
            return None
        return self.db.query(SharedChat).filter(SharedChat.token == token).first()

    def upsert(self, user_id: uuid.UUID, conversation: Conversation) -> SharedChat:
        """Create the share link, or refresh its snapshot (the token stays the same)."""
        snapshot = build_snapshot(list(conversation.messages))
        now = datetime.now(UTC)
        share = self.get_for_conversation(user_id, conversation.id)
        if share is None:
            share = SharedChat(
                user_id=user_id,
                conversation_id=conversation.id,
                token=secrets.token_urlsafe(TOKEN_BYTES),
                title=conversation.title,
                snapshot=snapshot,
            )
            self.db.add(share)
        else:
            share.title = conversation.title
            share.snapshot = snapshot
            share.updated_at = now
        self.db.commit()
        self.db.refresh(share)
        return share

    def delete(self, share: SharedChat) -> None:
        self.db.delete(share)
        self.db.commit()

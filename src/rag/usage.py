"""Per-user usage numbers for the dashboard."""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import Date, cast, func, literal_column
from sqlalchemy.orm import Session

from rag.db_models import Chunk, Collection, Conversation, Document, IngestJob, Message
from rag.ingest.jobs import ACTIVE_STATUSES, FAILED, SUCCEEDED

DAYS = 14
IMPORT_WINDOW_DAYS = 30


def _message_count(db: Session, user_id: uuid.UUID, *criteria: Any) -> int:
    query = (
        db.query(func.count(Message.id))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(Conversation.user_id == user_id, *criteria)
    )
    return int(query.scalar() or 0)


def _daily_questions(db: Session, user_id: uuid.UUID, today: date) -> list[dict[str, Any]]:
    start = today - timedelta(days=DAYS - 1)
    since = datetime.combine(start, time.min, tzinfo=UTC)
    day = cast(func.timezone(literal_column("'UTC'"), Message.created_at), Date)
    rows = (
        db.query(day, func.count(Message.id))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(
            Conversation.user_id == user_id,
            Message.role == "user",
            Message.created_at >= since,
        )
        .group_by(day)
        .all()
    )
    counts = {row_day: int(n) for row_day, n in rows}
    days = [start + timedelta(days=offset) for offset in range(DAYS)]
    return [{"date": d.isoformat(), "count": counts.get(d, 0)} for d in days]


def collect_usage(db: Session, user_id: uuid.UUID, today: date | None = None) -> dict[str, Any]:
    today = today or datetime.now(UTC).date()

    documents, characters = (
        db.query(func.count(Document.id), func.coalesce(func.sum(func.length(Document.content)), 0))
        .filter(Document.user_id == user_id)
        .one()
    )
    chunks = (
        db.query(func.count(Chunk.id))
        .join(Document, Document.id == Chunk.document_id)
        .filter(Document.user_id == user_id)
        .scalar()
    )
    collections = db.query(func.count(Collection.id)).filter(Collection.user_id == user_id).scalar()
    conversations = (
        db.query(func.count(Conversation.id)).filter(Conversation.user_id == user_id).scalar()
    )

    since = datetime.now(UTC) - timedelta(days=IMPORT_WINDOW_DAYS)
    import_rows = (
        db.query(IngestJob.status, func.count(IngestJob.id))
        .filter(IngestJob.user_id == user_id, IngestJob.created_at >= since)
        .group_by(IngestJob.status)
        .all()
    )
    imports = {status: int(n) for status, n in import_rows}

    return {
        "documents": int(documents),
        "chunks": int(chunks or 0),
        "characters": int(characters),
        "collections": int(collections or 0),
        "conversations": int(conversations or 0),
        "questions": _message_count(db, user_id, Message.role == "user"),
        "answers": _message_count(db, user_id, Message.role == "assistant"),
        "refused_answers": _message_count(
            db, user_id, Message.role == "assistant", Message.refused.is_(True)
        ),
        "feedback_up": _message_count(db, user_id, Message.feedback == 1),
        "feedback_down": _message_count(db, user_id, Message.feedback == -1),
        "imports": {
            "succeeded": imports.get(SUCCEEDED, 0),
            "failed": imports.get(FAILED, 0),
            "active": sum(n for status, n in imports.items() if status in ACTIVE_STATUSES),
        },
        "daily_questions": _daily_questions(db, user_id, today),
    }

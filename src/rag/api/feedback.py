import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from rag.api.deps import verify_api_key
from rag.api.schemas import FeedbackIn, FeedbackOut
from rag.auth.utils import get_current_user
from rag.chat_repository import ConversationRepository
from rag.db import get_db
from rag.db_models import Message, User

router = APIRouter(tags=["feedback"])

FEEDBACK_PATH = "/conversations/{conversation_id}/messages/{message_id}/feedback"


def _answer(db: Session, user: User, conversation_id: uuid.UUID, message_id: uuid.UUID) -> Message:
    message = ConversationRepository(db).get_message(user.id, conversation_id, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")
    if message.role != "assistant":
        raise HTTPException(status_code=422, detail="Only answers can be rated")
    return message


def _out(message: Message) -> FeedbackOut:
    return FeedbackOut(
        message_id=message.id, rating=message.feedback, comment=message.feedback_comment
    )


@router.put(FEEDBACK_PATH, response_model=FeedbackOut)
def rate_answer(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    payload: FeedbackIn,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> FeedbackOut:
    message = _answer(db, current_user, conversation_id, message_id)
    comment = (payload.comment or "").strip() or None
    updated = ConversationRepository(db).set_feedback(message, payload.rating, comment)
    return _out(updated)


@router.delete(FEEDBACK_PATH, response_model=FeedbackOut)
def clear_rating(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> FeedbackOut:
    message = _answer(db, current_user, conversation_id, message_id)
    return _out(ConversationRepository(db).set_feedback(message, None, None))

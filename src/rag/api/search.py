from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from rag.api.deps import limiter, verify_api_key
from rag.api.schemas import SearchHitOut
from rag.auth.utils import get_current_user
from rag.chat_repository import MAX_SEARCH_CHARS, ConversationRepository
from rag.db import get_db
from rag.db_models import User

router = APIRouter(tags=["search"])


@router.get("/search/conversations", response_model=list[SearchHitOut])
@limiter.limit("30/minute")
def search_conversations(
    request: Request,
    q: str = Query(..., min_length=1, max_length=MAX_SEARCH_CHARS),
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> list[SearchHitOut]:
    hits = ConversationRepository(db).search(current_user.id, q)
    return [
        SearchHitOut(
            id=hit.conversation.id,
            title=hit.conversation.title,
            pinned=hit.conversation.pinned,
            updated_at=hit.conversation.updated_at,
            snippet=hit.snippet,
        )
        for hit in hits
    ]

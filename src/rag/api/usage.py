from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from rag.api.deps import verify_api_key
from rag.api.query import QUERY_RATE_PER_MINUTE
from rag.api.schemas import UsageLimits, UsageOut
from rag.auth.utils import get_current_user
from rag.db import get_db
from rag.db_models import User
from rag.ingest.extractors import MAX_EXTRACTED_CHARS, MAX_UPLOAD_BYTES
from rag.ingest.jobs import MAX_ACTIVE_JOBS_PER_USER
from rag.usage import collect_usage

router = APIRouter(tags=["usage"])


@router.get("/usage", response_model=UsageOut)
def get_usage(
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> UsageOut:
    return UsageOut(
        **collect_usage(db, current_user.id),
        limits=UsageLimits(
            questions_per_minute=QUERY_RATE_PER_MINUTE,
            max_upload_mb=MAX_UPLOAD_BYTES // (1024 * 1024),
            max_document_chars=MAX_EXTRACTED_CHARS,
            max_active_imports=MAX_ACTIVE_JOBS_PER_USER,
        ),
    )

import logging
import uuid
from typing import NamedTuple

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from rag.api.deps import get_embedder, limiter, verify_api_key
from rag.api.schemas import IngestJobOut
from rag.auth.utils import get_current_user
from rag.db import get_db
from rag.db_models import IngestJob, User
from rag.ingest.extractors import (
    MAX_EXTRACTED_CHARS,
    MAX_UPLOAD_BYTES,
    UPLOAD_EXTENSIONS,
    ExtractionError,
)
from rag.ingest.jobs import (
    MAX_ACTIVE_JOBS_GLOBAL,
    MAX_ACTIVE_JOBS_PER_USER,
    MAX_TITLE_CHARS,
    MIN_TEXT_CHARS,
    FilePayload,
    JobPayload,
    JobRepository,
    JobRequest,
    TextPayload,
    UrlPayload,
    submit_job,
)
from rag.ingest.web import validate_url
from rag.repository import DocumentRepository
from rag.retrieve.embedder import Embedder

logger = logging.getLogger("rag.api.ingest_jobs")
router = APIRouter(prefix="/ingest/jobs", tags=["ingest-jobs"])


class _JobInput(NamedTuple):
    kind: str
    title: str  # as typed by the user, may be empty
    fallback_title: str  # shown until the real title is known
    collection_id: uuid.UUID | None
    payload: JobPayload


def _job_out(job: IngestJob) -> IngestJobOut:
    return IngestJobOut(
        id=job.id,
        kind=job.kind,
        title=job.title,
        status=job.status,
        stage=job.stage,
        progress_done=job.progress_done,
        progress_total=job.progress_total,
        document_id=job.document_id,
        duplicate=job.duplicate,
        error=job.error,
        created_at=job.created_at,
        finished_at=job.finished_at,
    )


def _parse_uuid(raw: object) -> uuid.UUID | None:
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid collection_id") from None


async def _read_input(request: Request) -> _JobInput:
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("application/json"):
        try:
            data = await request.json()
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid JSON body") from None
        if not isinstance(data, dict):
            raise HTTPException(status_code=422, detail="Invalid request body")

        title = str(data.get("title") or "").strip()[:MAX_TITLE_CHARS]
        collection_id = _parse_uuid(data.get("collection_id"))

        if data.get("url"):
            try:
                url = validate_url(str(data["url"]))
            except ExtractionError as e:
                raise HTTPException(status_code=422, detail=str(e)) from None
            return _JobInput("url", title, url, collection_id, UrlPayload(url))

        text = data.get("text")
        if isinstance(text, str):
            if len(text.strip()) < MIN_TEXT_CHARS:
                raise HTTPException(
                    status_code=422, detail="Text must be at least 10 characters long."
                )
            if len(text) > MAX_EXTRACTED_CHARS:
                raise HTTPException(status_code=413, detail="That text is too long.")
            return _JobInput("text", title, "Untitled", collection_id, TextPayload(text))
        raise HTTPException(status_code=422, detail="Provide either text or a url.")

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        file = form.get("file")
        if not isinstance(file, StarletteUploadFile):
            raise HTTPException(status_code=400, detail="Missing or invalid file upload")

        filename = (file.filename or "upload").lower()
        if not filename.endswith(UPLOAD_EXTENSIONS):
            raise HTTPException(
                status_code=415,
                detail="Unsupported file type. Use PDF, DOCX, PPTX, CSV, TXT, MD or an image.",
            )
        contents = await file.read()
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large. Max 10MB.")

        title = str(form.get("title") or "").strip()[:MAX_TITLE_CHARS]
        collection_id = _parse_uuid(form.get("collection_id"))
        stem = filename.rsplit(".", 1)[0] or filename
        return _JobInput("file", title, stem, collection_id, FilePayload(filename, contents))

    raise HTTPException(status_code=415, detail="Unsupported Media Type")


@router.post("", response_model=IngestJobOut, status_code=202)
@limiter.limit("10/minute")
async def create_job(
    request: Request,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> IngestJobOut:
    job_input = await _read_input(request)

    if job_input.collection_id is not None:
        lookup = DocumentRepository(db=db, embedder=embedder)
        if lookup.get_collection(current_user.id, job_input.collection_id) is None:
            raise HTTPException(status_code=404, detail="Collection not found")

    jobs = JobRepository(db)
    if jobs.count_active(current_user.id) >= MAX_ACTIVE_JOBS_PER_USER:
        raise HTTPException(
            status_code=429, detail="You already have imports in progress. Wait for one to finish."
        )
    if jobs.count_active() >= MAX_ACTIVE_JOBS_GLOBAL:
        raise HTTPException(
            status_code=503, detail="The server is busy importing. Please try again in a minute."
        )

    job = jobs.create(current_user.id, job_input.kind, job_input.title or job_input.fallback_title)
    created = _job_out(job)
    logger.info("Queued %s import job=%s user=%s", job_input.kind, job.id, current_user.username)
    submit_job(
        db.get_bind(),
        embedder,
        job.id,
        JobRequest(
            user_id=current_user.id,
            collection_id=job_input.collection_id,
            title=job_input.title,
            payload=job_input.payload,
        ),
    )
    return created


@router.get("", response_model=list[IngestJobOut])
def list_jobs(
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> list[IngestJobOut]:
    return [_job_out(job) for job in JobRepository(db).list_recent(current_user.id)]


@router.get("/{job_id}", response_model=IngestJobOut)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> IngestJobOut:
    job = JobRepository(db).get(current_user.id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Import not found")
    return _job_out(job)

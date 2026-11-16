"""Background ingestion jobs: extraction, chunking and embedding run off the request."""

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from google.genai import errors as genai_errors
from sqlalchemy import func, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from rag.db_models import IngestJob
from rag.ingest.extractors import ExtractionError, extract_upload_text
from rag.ingest.web import fetch_url
from rag.repository import DocumentRepository
from rag.retrieve.embedder import Embedder

logger = logging.getLogger("rag.ingest.jobs")

QUEUED, RUNNING, SUCCEEDED, FAILED = "queued", "running", "succeeded", "failed"
ACTIVE_STATUSES = (QUEUED, RUNNING)
EXTRACTING, EMBEDDING, SAVING, DONE = "extracting", "embedding", "saving", "done"

MAX_CONCURRENT_JOBS = 2
MAX_ACTIVE_JOBS_PER_USER = 3
MAX_ACTIVE_JOBS_GLOBAL = 20
RECENT_WINDOW = timedelta(hours=24)
RECENT_LIMIT = 10
MIN_TEXT_CHARS = 10
MAX_TITLE_CHARS = 255
MAX_SOURCE_CHARS = 1000

GENERIC_ERROR = "Import failed unexpectedly. Please try again."
AI_BUSY_ERROR = "The AI service is busy or unavailable. Please try again in a minute."
INTERRUPTED_ERROR = "The import was interrupted by a server restart. Please try again."


@dataclass(frozen=True)
class TextPayload:
    text: str


@dataclass(frozen=True)
class FilePayload:
    filename: str
    contents: bytes


@dataclass(frozen=True)
class UrlPayload:
    url: str


JobPayload = TextPayload | FilePayload | UrlPayload


@dataclass(frozen=True)
class JobRequest:
    user_id: uuid.UUID
    collection_id: uuid.UUID | None
    title: str  # what the user typed; empty means "derive it from the content"
    payload: JobPayload


class JobRepository:
    """Ingest job rows. Reads are always scoped by user."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, user_id: uuid.UUID, kind: str, title: str) -> IngestJob:
        job = IngestJob(user_id=user_id, kind=kind, title=title[:MAX_TITLE_CHARS])
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get(self, user_id: uuid.UUID, job_id: uuid.UUID) -> IngestJob | None:
        return (
            self.db.query(IngestJob)
            .filter(IngestJob.id == job_id, IngestJob.user_id == user_id)
            .first()
        )

    def list_recent(self, user_id: uuid.UUID) -> list[IngestJob]:
        since = datetime.now(UTC) - RECENT_WINDOW
        return (
            self.db.query(IngestJob)
            .filter(IngestJob.user_id == user_id, IngestJob.created_at >= since)
            .order_by(IngestJob.created_at.desc())
            .limit(RECENT_LIMIT)
            .all()
        )

    def count_active(self, user_id: uuid.UUID | None = None) -> int:
        query = self.db.query(func.count(IngestJob.id)).filter(
            IngestJob.status.in_(ACTIVE_STATUSES)
        )
        if user_id is not None:
            query = query.filter(IngestJob.user_id == user_id)
        return int(query.scalar() or 0)

    def update(self, job_id: uuid.UUID, **fields: Any) -> None:
        self.db.execute(
            update(IngestJob)
            .where(IngestJob.id == job_id)
            .values(updated_at=datetime.now(UTC), **fields)
        )
        self.db.commit()


def _read_input(request: JobRequest) -> tuple[str, str, str]:
    """Return (title, text, source) for the job, doing the slow extraction work."""
    payload = request.payload
    if isinstance(payload, UrlPayload):
        page = fetch_url(payload.url)
        host = urlsplit(payload.url).hostname or "Web page"
        return request.title or page.title or host, page.text, payload.url
    if isinstance(payload, FilePayload):
        text = extract_upload_text(payload.filename, payload.contents)
        stem = payload.filename.rsplit(".", 1)[0] or payload.filename
        source = f"uploaded:{payload.filename}"[:MAX_SOURCE_CHARS]
        return request.title or stem, text, source
    return request.title or "Untitled", payload.text, "manual_text_entry"


def _succeed(
    jobs: JobRepository, job_id: uuid.UUID, document_id: uuid.UUID, title: str, duplicate: bool
) -> None:
    jobs.update(
        job_id,
        status=SUCCEEDED,
        stage=DONE,
        document_id=document_id,
        title=title[:MAX_TITLE_CHARS],
        duplicate=duplicate,
        error=None,
        finished_at=datetime.now(UTC),
    )


def _fail(jobs: JobRepository, job_id: uuid.UUID, message: str) -> None:
    jobs.update(job_id, status=FAILED, error=message, finished_at=datetime.now(UTC))


def _execute(session: Session, embedder: Embedder, job_id: uuid.UUID, request: JobRequest) -> None:
    jobs = JobRepository(session)
    jobs.update(job_id, status=RUNNING, stage=EXTRACTING)
    try:
        title, text, source = _read_input(request)
        if len(text.strip()) < MIN_TEXT_CHARS:
            raise ExtractionError("No readable text was found in this document.")
        title = title.strip()[:MAX_TITLE_CHARS] or "Untitled"
        repo = DocumentRepository(db=session, embedder=embedder)

        existing = repo.find_existing(request.user_id, text)
        if existing is not None:
            _succeed(jobs, job_id, existing.id, existing.title, duplicate=True)
            return

        def on_progress(done: int, total: int) -> None:
            stage = EMBEDDING if done < total else SAVING
            jobs.update(job_id, stage=stage, progress_done=done, progress_total=total)

        document = repo.ingest_document(
            user_id=request.user_id,
            title=title,
            text=text,
            source_url=source,
            collection_id=request.collection_id,
            on_progress=on_progress,
        )
        _succeed(jobs, job_id, document.id, document.title, duplicate=False)
    except ExtractionError as e:
        session.rollback()
        _fail(jobs, job_id, str(e))
    except genai_errors.APIError as e:
        session.rollback()
        logger.error("[job %s] Gemini error code=%s: %s", job_id, e.code, e)
        _fail(jobs, job_id, AI_BUSY_ERROR)
    except Exception:
        session.rollback()
        logger.exception("[job %s] failed", job_id)
        _fail(jobs, job_id, GENERIC_ERROR)


def run_ingest_job(
    bind: Engine | Connection, embedder: Embedder, job_id: uuid.UUID, request: JobRequest
) -> None:
    try:
        with Session(bind) as session:
            _execute(session, embedder, job_id, request)
    except Exception:
        logger.exception("[job %s] crashed", job_id)
        try:
            with Session(bind) as session:
                _fail(JobRepository(session), job_id, GENERIC_ERROR)
        except Exception:
            logger.exception("[job %s] could not record the failure", job_id)


# A small pool: queued jobs wait here without holding request threads or memory-heavy work.
_EXECUTOR = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS, thread_name_prefix="ingest")


def submit_job(
    bind: Engine | Connection, embedder: Embedder, job_id: uuid.UUID, request: JobRequest
) -> None:
    _EXECUTOR.submit(run_ingest_job, bind, embedder, job_id, request)


def shutdown_workers() -> None:
    _EXECUTOR.shutdown(wait=False, cancel_futures=True)


def fail_interrupted_jobs(bind: Engine | Connection) -> None:
    """On startup, jobs still marked active were killed by a restart: mark them failed."""
    try:
        with Session(bind) as session:
            now = datetime.now(UTC)
            session.execute(
                update(IngestJob)
                .where(IngestJob.status.in_(ACTIVE_STATUSES))
                .values(status=FAILED, error=INTERRUPTED_ERROR, finished_at=now, updated_at=now)
            )
            session.commit()
    except Exception:
        logger.warning("Could not clean up interrupted ingest jobs", exc_info=True)

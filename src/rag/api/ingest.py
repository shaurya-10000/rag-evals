import logging
import uuid
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Request
from google.genai import errors as genai_errors
from pypdf import PdfReader
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from rag.api.deps import get_embedder, limiter, verify_api_key
from rag.api.schemas import IngestResponse
from rag.api.vision import VisionError, describe_image
from rag.auth.utils import get_current_user
from rag.db import get_db
from rag.db_models import User
from rag.repository import DocumentRepository
from rag.retrieve.embedder import Embedder

logger = logging.getLogger("rag.api.ingest")
router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


def _extract_pdf_text(contents: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(contents))
        pages = (page.extract_text() for page in reader.pages)
        return "\n".join(text for text in pages if text)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid PDF file") from e


def _extract_upload_text(filename: str, contents: bytes) -> str:
    if filename.endswith(".pdf"):
        return _extract_pdf_text(contents)
    if filename.endswith(IMAGE_EXTENSIONS):
        try:
            return describe_image(filename, contents)
        except VisionError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
    try:
        return contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400, detail="File must be UTF-8 text, PDF, or Image"
        ) from None


async def _read_payload(request: Request) -> tuple[str, str, str]:
    """Return (title, text, source) from a JSON body or a multipart upload."""
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("application/json"):
        data = await request.json()
        title = str(data.get("title", "Untitled"))
        text = str(data.get("text", ""))
        if len(text.strip()) < 10:
            raise HTTPException(status_code=422, detail="Text must be at least 10 characters long.")
        return title, text, "manual_text_entry"

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        title = str(form.get("title", "Untitled"))
        file = form.get("file")
        if not isinstance(file, StarletteUploadFile):
            raise HTTPException(status_code=400, detail="Missing or invalid file upload")

        contents = await file.read()
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large. Max 10MB.")

        filename = (file.filename or "unknown").lower()
        text = _extract_upload_text(filename, contents)
        if not text.strip():
            raise HTTPException(status_code=400, detail="Extracted text is empty")
        return title, text, f"uploaded:{filename}"

    raise HTTPException(status_code=415, detail="Unsupported Media Type")


@router.post("/ingest", response_model=IngestResponse)
@limiter.limit("3/minute")
async def ingest(
    request: Request,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> IngestResponse:
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] Ingest started for user={current_user.username}")

    title, text, source = await _read_payload(request)

    try:
        repo = DocumentRepository(db=db, embedder=embedder)
        doc = repo.ingest_document(
            user_id=current_user.id, title=title, text=text, source_url=source
        )
        logger.info(f"[{request_id}] Ingest done. doc_id={doc.id}")
        return IngestResponse(document_id=doc.id, status="ingested")
    except genai_errors.APIError:
        raise
    except Exception as e:
        logger.error(f"[{request_id}] Ingest failed: {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail="Ingest failed. Please try again.") from e

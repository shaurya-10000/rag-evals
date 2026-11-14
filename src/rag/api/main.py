import base64
import json
import logging
import os
import time
import uuid
from collections.abc import AsyncGenerator
from collections.abc import Generator as TypingGenerator
from contextlib import asynccontextmanager
from functools import lru_cache
from io import BytesIO

from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from google import genai
from google.genai import types
from pypdf import PdfReader
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from rag.api.auth import router as auth_router
from rag.api.schemas import IngestResponse, QueryRequest
from rag.config.settings import settings
from rag.db import get_db
from rag.generate.generator import Generator
from rag.generate.reranker import Reranker
from rag.repository import DocumentRepository
from rag.retrieve.embedder import Embedder
from rag.retrieve.retriever import Retriever

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rag.api")

RERANK_CANDIDATES = int(os.getenv("RERANK_CANDIDATES", "10"))
VISION_TIMEOUT_MS = 15000
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if api_key != settings.RAG_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return Embedder(mock=False)


@lru_cache(maxsize=1)
def get_generator() -> Generator:
    return Generator(mock=False)


@lru_cache(maxsize=1)
def get_reranker() -> Reranker:
    enabled = os.getenv("RERANK_ENABLED", "true").lower() != "false"
    return Reranker(mock=not enabled)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    if os.getenv("RERANK_ENABLED", "true").lower() != "false":
        logger.info("Pre-loading reranker model into memory...")
        get_reranker()._get_model()
        logger.info("Reranker model loaded successfully.")
    yield


app = FastAPI(title="RAG Evals API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.include_router(auth_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
@limiter.limit("3/minute")
async def ingest(
    request: Request,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    _: str = Depends(verify_api_key),
) -> IngestResponse:
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] Ingest started")

    content_type = request.headers.get("content-type", "")
    text = ""
    title = ""
    source = ""

    if content_type.startswith("application/json"):
        data = await request.json()
        title = data.get("title", "Untitled")
        text = data.get("text", "")
        source = "manual_text_entry"
        if len(text.strip()) < 10:
            raise HTTPException(
                status_code=422, detail="Text must be at least 10 characters long."
            )
    elif content_type.startswith("multipart/form-data"):
        form = await request.form()
        title = str(form.get("title", "Untitled"))
        file = form.get("file")
        if not isinstance(file, StarletteUploadFile):
            raise HTTPException(status_code=400, detail="Missing or invalid file upload")

        contents = await file.read()
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large. Max 10MB.")

        filename = (file.filename or "unknown").lower()
        source = f"uploaded:{filename}"

        if filename.endswith(".pdf"):
            try:
                reader = PdfReader(BytesIO(contents))
                text = "\n".join(
                    p.extract_text() for p in reader.pages if p.extract_text()
                )
            except Exception as e:
                raise HTTPException(status_code=400, detail="Invalid PDF file") from e
        elif filename.endswith((".png", ".jpg", ".jpeg", ".webp")):
            client = genai.Client(
                api_key=settings.GEMINI_API_KEY,
                http_options=types.HttpOptions(timeout=VISION_TIMEOUT_MS),
            )
            mime_type = (
                "image/jpeg"
                if filename.endswith((".jpg", ".jpeg"))
                else f"image/{filename.split('.')[-1]}"
            )
            b64_img = base64.b64encode(contents).decode("utf-8")
            prompt = "Describe this image in extreme detail. Output only the description."
            for model in ["gemini-3.8-flash", "gemini-3.5-flash-lite"]:
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=types.Content(
                            parts=[
                                types.Part.from_bytes(
                                    data=base64.b64decode(b64_img),
                                    mime_type=mime_type,
                                ),
                                types.Part.from_text(text=prompt),
                            ]
                        ),
                    )
                    if response.text:
                        text = f"Image Description ({filename}):\n{response.text}"
                        break
                except Exception:
                    continue
            if not text:
                raise HTTPException(status_code=500, detail="All vision models failed.")
        else:
            try:
                text = contents.decode("utf-8")
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=400, detail="File must be UTF-8 text, PDF, or Image"
                ) from None

        if not text.strip():
            raise HTTPException(status_code=400, detail="Extracted text is empty")
    else:
        raise HTTPException(status_code=415, detail="Unsupported Media Type")

    repo = DocumentRepository(db=db, embedder=embedder)
    doc = repo.ingest_document(title=title, text=text, source_url=source)
    logger.info(f"[{request_id}] Ingest done. doc_id={doc.id}")
    return IngestResponse(document_id=doc.id, status="ingested")


@app.post("/query")
@limiter.limit("5/minute")
def query(
    request: Request,
    payload: QueryRequest,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    generator: Generator = Depends(get_generator),
    reranker: Reranker = Depends(get_reranker),
    _: str = Depends(verify_api_key),
) -> StreamingResponse:
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] Query: '{payload.query[:60]}'")

    t_start = time.perf_counter()
    retriever = Retriever(db=db, embedder=embedder)
    candidates = retriever.search(query=payload.query, top_k=RERANK_CANDIDATES)
    t_retrieve = time.perf_counter()

    final_chunks = reranker.rerank(
        query=payload.query, chunks=candidates, top_k=payload.top_k
    )
    t_rerank = time.perf_counter()

    def event_generator() -> TypingGenerator[str, None, None]:
        sources = [
            {"id": str(c.id), "content": c.content, "metadata": c.metadata_col}
            for c in final_chunks
        ]
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
        try:
            for text_chunk in generator.stream_answer(
                query=payload.query, chunks=final_chunks
            ):
                yield f"data: {json.dumps({'type': 'token', 'text': text_chunk})}\n\n"
        except Exception as e:
            logger.error(f"[{request_id}] Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return
        t_generate = time.perf_counter()

        def ms(a: float, b: float) -> int:
            return round((b - a) * 1000)

        timings = (
            f"retrieve={ms(t_start, t_retrieve)}ms "
            f"rerank={ms(t_retrieve, t_rerank)}ms "
            f"generate={ms(t_rerank, t_generate)}ms"
        )
        logger.info(f"[{request_id}] Done. {timings}")
        yield f"data: {json.dumps({'type': 'done', 'timings': timings})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


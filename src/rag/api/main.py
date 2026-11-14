import base64
import json
import logging
import os
import time
from collections.abc import AsyncGenerator
from collections.abc import Generator as TypingGenerator
from contextlib import asynccontextmanager
from functools import lru_cache
from io import BytesIO

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from google import genai
from google.genai import types
from pypdf import PdfReader
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from rag.api.schemas import IngestResponse, QueryRequest
from rag.config.settings import settings
from rag.db import get_db
from rag.generate.generator import Generator
from rag.generate.reranker import Reranker
from rag.repository import DocumentRepository
from rag.retrieve.embedder import Embedder
from rag.retrieve.retriever import Retriever

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag.api")

RERANK_CANDIDATES = int(os.getenv("RERANK_CANDIDATES", "10"))
VISION_TIMEOUT_MS = 15000


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


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
async def ingest(
    request: Request,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
) -> IngestResponse:
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
        title_val = form.get("title", "Untitled")
        title = str(title_val)
        file = form.get("file")

        if not isinstance(file, StarletteUploadFile):
            raise HTTPException(status_code=400, detail="Missing or invalid file upload")

        contents = await file.read()
        filename = (file.filename or "unknown").lower()
        source = f"uploaded:{filename}"

        if filename.endswith(".pdf"):
            try:
                reader = PdfReader(BytesIO(contents))
                text = "\n".join(
                    page.extract_text() for page in reader.pages if page.extract_text()
                )
            except Exception as e:
                raise HTTPException(status_code=400, detail="Invalid PDF file") from e

        elif filename.endswith((".png", ".jpg", ".jpeg", ".webp")):
            client = genai.Client(
                api_key=settings.GEMINI_API_KEY,
                http_options=types.HttpOptions(timeout=VISION_TIMEOUT_MS),
            )
            if filename.endswith((".jpg", ".jpeg")):
                mime_type = "image/jpeg"
            else:
                mime_type = f"image/{filename.split('.')[-1]}"

            b64_img = base64.b64encode(contents).decode("utf-8")
            prompt = (
                "Describe this image in extreme detail. "
                "Include any text, charts, code, or key visual information. "
                "Output only the description."
            )
            vision_models = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]

            for model in vision_models:
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=types.Content(
                            parts=[
                                types.Part.from_bytes(
                                    data=base64.b64decode(b64_img), mime_type=mime_type
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
    return IngestResponse(document_id=doc.id, status="ingested")


@app.post("/query")
def query(
    request: QueryRequest,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    generator: Generator = Depends(get_generator),
    reranker: Reranker = Depends(get_reranker),
) -> StreamingResponse:
    t_start = time.perf_counter()

    retriever = Retriever(db=db, embedder=embedder)
    candidates = retriever.search(query=request.query, top_k=RERANK_CANDIDATES)
    t_retrieve = time.perf_counter()

    final_chunks = reranker.rerank(
        query=request.query, chunks=candidates, top_k=request.top_k
    )
    t_rerank = time.perf_counter()

    def event_generator() -> TypingGenerator[str, None, None]:
        # 1. Send the Sources (metadata) first
        sources = [
            {"id": str(c.id), "content": c.content, "metadata": c.metadata_col}
            for c in final_chunks
        ]
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        # 2. Stream the answer token by token
        try:
            for text_chunk in generator.stream_answer(
                query=request.query, chunks=final_chunks
            ):
                yield f"data: {json.dumps({'type': 'token', 'text': text_chunk})}\n\n"
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        # 3. Send completion signal
        t_generate = time.perf_counter()

        def ms(a: float, b: float) -> int:
            return round((b - a) * 1000)

        timings = (
            f"retrieve={ms(t_start, t_retrieve)}ms "
            f"rerank={ms(t_retrieve, t_rerank)}ms "
            f"generate={ms(t_rerank, t_generate)}ms"
        )
        logger.info("query timings: %s (candidates=%d)", timings, len(candidates))
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

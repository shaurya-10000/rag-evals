import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from google.genai import errors as genai_errors
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from rag.api import (
    conversations,
    documents,
    feedback,
    ingest,
    ingest_jobs,
    query,
    search,
    shares,
    title,
    usage,
)
from rag.api.auth import router as auth_router
from rag.api.deps import get_reranker, limiter
from rag.db import engine
from rag.ingest.jobs import fail_interrupted_jobs, shutdown_workers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rag.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    if os.getenv("RERANK_ENABLED", "true").lower() != "false":
        logger.info("Pre-loading reranker model into memory...")
        get_reranker()._get_model()
        logger.info("Reranker model loaded successfully.")
    fail_interrupted_jobs(engine)
    yield
    shutdown_workers()


app = FastAPI(title="RAG Evals API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

app.include_router(auth_router)
app.include_router(ingest.router)
app.include_router(ingest_jobs.router)
app.include_router(feedback.router)
app.include_router(search.router)
app.include_router(shares.router)
app.include_router(usage.router)
app.include_router(query.router)
app.include_router(title.router)
app.include_router(documents.router)
app.include_router(conversations.router)


@app.exception_handler(genai_errors.APIError)
async def ai_service_error_handler(request: Request, exc: genai_errors.APIError) -> JSONResponse:
    logger.error("Gemini API error code=%s path=%s: %s", exc.code, request.url.path, exc)
    if exc.code == 429:
        detail = "The AI service is busy right now. Please try again in a minute."
        return JSONResponse(status_code=503, content={"detail": detail})
    return JSONResponse(
        status_code=502,
        content={"detail": "The AI service had a problem. Please try again."},
    )


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

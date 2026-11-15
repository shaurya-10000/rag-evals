import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from rag.api import ingest, query, title
from rag.api.auth import router as auth_router
from rag.api.deps import get_reranker, limiter

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
    yield


app = FastAPI(title="RAG Evals API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

app.include_router(auth_router)
app.include_router(ingest.router)
app.include_router(query.router)
app.include_router(title.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

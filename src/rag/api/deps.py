import os
import secrets
from functools import lru_cache

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address

from rag.config.settings import settings
from rag.generate.generator import Generator
from rag.generate.reranker import Reranker
from rag.retrieve.embedder import Embedder

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    expected = settings.RAG_API_KEY.encode()
    if not api_key or not secrets.compare_digest(api_key.encode(), expected):
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

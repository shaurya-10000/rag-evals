import json
import logging
import os
import time
import uuid
from collections.abc import Generator as TypingGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from rag.api.deps import get_embedder, get_generator, get_reranker, limiter, verify_api_key
from rag.api.schemas import QueryRequest
from rag.auth.utils import get_current_user
from rag.db import get_db
from rag.db_models import User
from rag.generate.generator import Generator
from rag.generate.reranker import Reranker
from rag.retrieve.embedder import Embedder
from rag.retrieve.retriever import Retriever

logger = logging.getLogger("rag.api.query")
router = APIRouter()

RERANK_CANDIDATES = int(os.getenv("RERANK_CANDIDATES", "10"))


@router.post("/query")
@limiter.limit("5/minute")
def query(
    request: Request,
    payload: QueryRequest,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    generator: Generator = Depends(get_generator),
    reranker: Reranker = Depends(get_reranker),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] Query from user={current_user.username}: '{payload.query[:60]}'")

    t_start = time.perf_counter()
    retriever = Retriever(db=db, embedder=embedder)
    candidates = retriever.search(
        query=payload.query, user_id=current_user.id, top_k=RERANK_CANDIDATES
    )
    t_retrieve = time.perf_counter()

    final_chunks = reranker.rerank(query=payload.query, chunks=candidates, top_k=payload.top_k)
    t_rerank = time.perf_counter()

    def event_generator() -> TypingGenerator[str, None, None]:
        sources = [
            {"id": str(c.id), "content": c.content, "metadata": c.metadata_col}
            for c in final_chunks
        ]
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
        try:
            for text_chunk in generator.stream_answer(query=payload.query, chunks=final_chunks):
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

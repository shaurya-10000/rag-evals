import json
import logging
import os
import time
import uuid
from collections.abc import Generator as TypingGenerator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from rag.api.deps import get_embedder, get_generator, get_reranker, limiter, verify_api_key
from rag.api.schemas import QueryRequest
from rag.auth.utils import get_current_user
from rag.chat_repository import ConversationRepository
from rag.db import get_db
from rag.db_models import Chunk, User
from rag.generate.generator import Generator
from rag.generate.reranker import Reranker
from rag.retrieve.embedder import Embedder
from rag.retrieve.retriever import Retriever

logger = logging.getLogger("rag.api.query")
router = APIRouter()

RERANK_CANDIDATES = int(os.getenv("RERANK_CANDIDATES", "10"))


def _source_payload(chunk: Chunk) -> dict[str, Any]:
    """Citation snapshot: stays readable even if the document is later edited or deleted."""
    document = chunk.document
    return {
        "id": str(chunk.id),
        "document_id": str(document.id),
        "document_title": document.title,
        "content": chunk.content,
        "metadata": chunk.metadata_col,
    }


def _persist_assistant_message(
    bind: Engine | Connection,
    conversation_id: uuid.UUID,
    content: str,
    sources: list[dict[str, Any]],
    request_id: str,
) -> None:
    """Save the answer with its own session: the request-scoped one may already be closed."""
    try:
        with Session(bind) as session:
            ConversationRepository(session).add_message(
                conversation_id, "assistant", content, sources
            )
    except Exception:
        logger.exception("[%s] Failed to persist assistant message", request_id)


def _ms(start: float, end: float) -> int:
    return round((end - start) * 1000)


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

    conversation_id = payload.conversation_id
    conversations = ConversationRepository(db)
    if conversation_id is not None and conversations.get(current_user.id, conversation_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    t_start = time.perf_counter()
    retriever = Retriever(db=db, embedder=embedder)
    candidates = retriever.search(
        query=payload.query,
        user_id=current_user.id,
        top_k=RERANK_CANDIDATES,
        collection_id=payload.collection_id,
    )
    t_retrieve = time.perf_counter()

    final_chunks = reranker.rerank(query=payload.query, chunks=candidates, top_k=payload.top_k)
    t_rerank = time.perf_counter()

    sources = [_source_payload(c) for c in final_chunks]
    bind = db.get_bind()

    # Persist the question only once retrieval succeeded, so a failed lookup leaves no orphan.
    if conversation_id is not None:
        conversations.add_message(conversation_id, "user", payload.query, [])

    def event_generator() -> TypingGenerator[str, None, None]:
        answer_parts: list[str] = []
        try:
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
            try:
                for text_chunk in generator.stream_answer(query=payload.query, chunks=final_chunks):
                    answer_parts.append(text_chunk)
                    yield f"data: {json.dumps({'type': 'token', 'text': text_chunk})}\n\n"
            except Exception as e:
                logger.error(f"[{request_id}] Stream error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                return
            t_generate = time.perf_counter()

            timings = (
                f"retrieve={_ms(t_start, t_retrieve)}ms "
                f"rerank={_ms(t_retrieve, t_rerank)}ms "
                f"generate={_ms(t_rerank, t_generate)}ms"
            )
            logger.info(f"[{request_id}] Done. {timings}")
            yield f"data: {json.dumps({'type': 'done', 'timings': timings})}\n\n"
        finally:
            # Runs on success, on stream errors and when the client disconnects mid-answer.
            answer = "".join(answer_parts)
            if conversation_id is not None and answer:
                _persist_assistant_message(bind, conversation_id, answer, sources, request_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

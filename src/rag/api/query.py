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

from rag.api.deps import (
    get_embedder,
    get_generator,
    get_reranker,
    get_rewriter,
    limiter,
    verify_api_key,
)
from rag.api.schemas import QueryRequest
from rag.auth.utils import get_current_user
from rag.chat_repository import ConversationRepository
from rag.db import get_db
from rag.db_models import Chunk, Conversation, User
from rag.generate.generator import Generator
from rag.generate.relevance import should_refuse
from rag.generate.reranker import Reranker
from rag.generate.rewriter import MAX_HISTORY_MESSAGES, HistoryMessage, QueryRewriter
from rag.retrieve.embedder import Embedder
from rag.retrieve.retriever import Retriever

logger = logging.getLogger("rag.api.query")
router = APIRouter()

RERANK_CANDIDATES = int(os.getenv("RERANK_CANDIDATES", "10"))
QUERY_RATE_PER_MINUTE = 5


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


def _history(conversation: Conversation | None) -> list[HistoryMessage]:
    """Recent messages of the conversation, taken before the new question is stored."""
    if conversation is None:
        return []
    recent = list(conversation.messages)[-MAX_HISTORY_MESSAGES:]
    return [HistoryMessage(role=m.role, content=m.content) for m in recent]


def _persist_assistant_message(
    bind: Engine | Connection,
    message_id: uuid.UUID,
    conversation_id: uuid.UUID,
    content: str,
    sources: list[dict[str, Any]],
    request_id: str,
    rewritten_query: str | None,
    refused: bool,
) -> bool:
    """Save the answer with its own session: the request-scoped one may already be closed."""
    try:
        with Session(bind) as session:
            ConversationRepository(session).add_message(
                conversation_id,
                "assistant",
                content,
                sources,
                rewritten_query=rewritten_query,
                refused=refused,
                message_id=message_id,
            )
    except Exception:
        logger.exception("[%s] Failed to persist assistant message", request_id)
        return False
    return True


def _ms(start: float, end: float) -> int:
    return round((end - start) * 1000)


@router.post("/query")
@limiter.limit(f"{QUERY_RATE_PER_MINUTE}/minute")
def query(
    request: Request,
    payload: QueryRequest,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    generator: Generator = Depends(get_generator),
    reranker: Reranker = Depends(get_reranker),
    rewriter: QueryRewriter = Depends(get_rewriter),
    _: str = Depends(verify_api_key),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] Query from user={current_user.username}: '{payload.query[:60]}'")

    conversation_id = payload.conversation_id
    conversations = ConversationRepository(db)
    conversation: Conversation | None = None
    if conversation_id is not None:
        conversation = conversations.get(current_user.id, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
    history = _history(conversation)

    t_start = time.perf_counter()
    # Follow-ups like "what about its pricing?" need the conversation to be searchable.
    search_query = rewriter.rewrite(payload.query, history)
    rewritten = search_query != payload.query
    if rewritten:
        logger.info(f"[{request_id}] Rewrote query -> '{search_query[:80]}'")
    t_rewrite = time.perf_counter()

    retriever = Retriever(db=db, embedder=embedder)
    candidates = retriever.search(
        query=search_query,
        user_id=current_user.id,
        top_k=RERANK_CANDIDATES,
        collection_id=payload.collection_id,
    )
    t_retrieve = time.perf_counter()

    final_chunks, best_score = reranker.rerank_scored(
        query=search_query, chunks=candidates, top_k=payload.top_k
    )
    refused = should_refuse(best_score)
    if refused:
        # Nothing relevant: skip generation (saves quota) and say so instead of guessing.
        final_chunks = []
    t_rerank = time.perf_counter()
    logger.info(f"[{request_id}] best_rerank_score={best_score} refused={refused}")

    sources = [_source_payload(c) for c in final_chunks]
    bind = db.get_bind()
    message_id = uuid.uuid4()
    rewritten_query = search_query if rewritten else None

    # Persist the question only once retrieval succeeded, so a failed lookup leaves no orphan.
    if conversation_id is not None:
        conversations.add_message(conversation_id, "user", payload.query, [])

    def persist(answer: str) -> bool:
        if conversation_id is None or not answer:
            return False
        return _persist_assistant_message(
            bind,
            message_id,
            conversation_id,
            answer,
            sources,
            request_id,
            rewritten_query,
            refused,
        )

    def event_generator() -> TypingGenerator[str, None, None]:
        answer_parts: list[str] = []
        saved = False
        try:
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
            try:
                for text_chunk in generator.stream_answer(query=search_query, chunks=final_chunks):
                    answer_parts.append(text_chunk)
                    yield f"data: {json.dumps({'type': 'token', 'text': text_chunk})}\n\n"
            except Exception as e:
                logger.error(f"[{request_id}] Stream error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                return
            t_generate = time.perf_counter()

            # Save before announcing "done", so the id the client receives already exists.
            saved = persist("".join(answer_parts))

            timings = (
                f"rewrite={_ms(t_start, t_rewrite)}ms "
                f"retrieve={_ms(t_rewrite, t_retrieve)}ms "
                f"rerank={_ms(t_retrieve, t_rerank)}ms "
                f"generate={_ms(t_rerank, t_generate)}ms"
            )
            logger.info(f"[{request_id}] Done. {timings}")
            done = {
                "type": "done",
                "timings": timings,
                "rewritten_query": rewritten_query,
                "refused": refused,
                "message_id": str(message_id) if saved else None,
            }
            yield f"data: {json.dumps(done)}\n\n"
        finally:
            # Covers stream errors and clients that disconnect mid-answer.
            if not saved:
                persist("".join(answer_parts))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

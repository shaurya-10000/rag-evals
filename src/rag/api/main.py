import os
from functools import lru_cache

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from rag.api.schemas import ChunkResult, IngestRequest, IngestResponse, QueryRequest, QueryResponse
from rag.db import get_db
from rag.generate.generator import Generator
from rag.generate.reranker import Reranker
from rag.repository import DocumentRepository
from rag.retrieve.embedder import Embedder
from rag.retrieve.retriever import Retriever

app = FastAPI(title="RAG Evals API", version="0.1.0")

def get_embedder() -> Embedder:
    return Embedder(mock=False)

def get_generator() -> Generator:
    return Generator(mock=False)

@lru_cache(maxsize=1)
def get_reranker() -> Reranker:
    enabled = os.getenv("RERANK_ENABLED", "true").lower() != "false"
    return Reranker(mock=not enabled)

@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/ingest", response_model=IngestResponse)
def ingest(
    request: IngestRequest,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
) -> IngestResponse:
    repo = DocumentRepository(db=db, embedder=embedder)
    doc = repo.ingest_document(
        title=request.title, text=request.text, source_url=request.source_url
    )
    return IngestResponse(document_id=doc.id, status="ingested")

@app.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    generator: Generator = Depends(get_generator),
    reranker: Reranker = Depends(get_reranker),
) -> QueryResponse:
    # 1. Retrieve 20 candidates via Hybrid Search
    retriever = Retriever(db=db, embedder=embedder)
    candidates = retriever.search(query=request.query, top_k=20)
    
    # 2. Rerank down to the best 3
    final_chunks = reranker.rerank(query=request.query, chunks=candidates, top_k=request.top_k)
    
    # 3. Generate answer using the reranked chunks
    answer = generator.generate_answer(query=request.query, chunks=final_chunks)
    
    results = [
        ChunkResult(id=c.id, content=c.content, metadata=c.metadata_col)
        for c in final_chunks
    ]
    return QueryResponse(answer=answer, results=results)

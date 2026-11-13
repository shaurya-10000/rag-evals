from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from rag.api.schemas import ChunkResult, IngestRequest, IngestResponse, QueryRequest, QueryResponse
from rag.db import get_db
from rag.generate.generator import Generator
from rag.repository import DocumentRepository
from rag.retrieve.embedder import Embedder
from rag.retrieve.retriever import Retriever

app = FastAPI(title="RAG Evals API", version="0.1.0")

def get_embedder() -> Embedder:
    return Embedder(mock=False)

def get_generator() -> Generator:
    return Generator(mock=False)

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
) -> QueryResponse:
    retriever = Retriever(db=db, embedder=embedder)
    chunks = retriever.search(query=request.query, top_k=request.top_k)
    
    # Generate answer using the retrieved chunks
    answer = generator.generate_answer(query=request.query, chunks=chunks)
    
    results = [
        ChunkResult(id=c.id, content=c.content, metadata=c.metadata_col)
        for c in chunks
    ]
    return QueryResponse(answer=answer, results=results)

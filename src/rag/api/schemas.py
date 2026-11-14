from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    document_id: UUID
    status: str


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=2)
    top_k: int = Field(default=5, ge=1, le=20)


class ChunkResult(BaseModel):
    id: UUID
    content: str
    metadata: dict[str, Any]


class QueryResponse(BaseModel):
    answer: str
    results: list[ChunkResult]

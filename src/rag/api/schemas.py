from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

MAX_CONTENT_CHARS = 500_000


class IngestResponse(BaseModel):
    document_id: UUID
    status: str


class TitleRequest(BaseModel):
    prompt: str


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=2)
    top_k: int = Field(default=5, ge=1, le=20)
    collection_id: UUID | None = None


class ChunkResult(BaseModel):
    id: UUID
    content: str
    metadata: dict[str, Any]


class QueryResponse(BaseModel):
    answer: str
    results: list[ChunkResult]


class DocumentSummary(BaseModel):
    id: UUID
    title: str
    collection_id: UUID | None
    source_url: str | None
    preview: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class DocumentDetail(DocumentSummary):
    content: str


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    content: str | None = Field(default=None, max_length=MAX_CONTENT_CHARS)


class MoveRequest(BaseModel):
    collection_id: UUID | None = None


class CollectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class CollectionUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class CollectionOut(BaseModel):
    id: UUID
    name: str
    document_count: int
    created_at: datetime

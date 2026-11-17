from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

MAX_CONTENT_CHARS = 500_000
MAX_MESSAGE_CHARS = 100_000
MAX_IMPORT_CONVERSATIONS = 100
MAX_IMPORT_MESSAGES = 500
MAX_SOURCES_PER_MESSAGE = 20


class IngestResponse(BaseModel):
    document_id: UUID
    status: str


class TitleRequest(BaseModel):
    prompt: str


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=2)
    top_k: int = Field(default=5, ge=1, le=20)
    collection_id: UUID | None = None
    conversation_id: UUID | None = None


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


# ---------------------------------------------------------------- conversations
class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    pinned: bool | None = None


class ConversationOut(BaseModel):
    id: UUID
    title: str
    pinned: bool
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    sources: list[dict[str, Any]]
    created_at: datetime
    rewritten_query: str | None = None
    refused: bool = False
    feedback: int | None = None
    feedback_comment: str | None = None


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class ImportMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)
    sources: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_SOURCES_PER_MESSAGE)


class ImportConversation(BaseModel):
    title: str = Field(default="New Chat", max_length=255)
    pinned: bool = False
    created_at: datetime
    messages: list[ImportMessage] = Field(..., min_length=1, max_length=MAX_IMPORT_MESSAGES)


class ImportRequest(BaseModel):
    conversations: list[ImportConversation] = Field(..., max_length=MAX_IMPORT_CONVERSATIONS)


class ImportResponse(BaseModel):
    imported: int


# ---------------------------------------------------------------- ingest jobs
class IngestJobOut(BaseModel):
    id: UUID
    kind: str
    title: str
    status: str
    stage: str
    progress_done: int
    progress_total: int
    document_id: UUID | None
    duplicate: bool
    error: str | None
    created_at: datetime
    finished_at: datetime | None


# ---------------------------------------------------------------- feedback, search, sharing
class FeedbackIn(BaseModel):
    rating: Literal[-1, 1]
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackOut(BaseModel):
    message_id: UUID
    rating: int | None
    comment: str | None


class SearchHitOut(BaseModel):
    id: UUID
    title: str
    pinned: bool
    updated_at: datetime
    snippet: str | None


class ShareOut(BaseModel):
    shared: bool
    token: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SharedSource(BaseModel):
    document_title: str | None = None
    content: str


class SharedMessage(BaseModel):
    role: str
    content: str
    sources: list[SharedSource]


class SharedChatOut(BaseModel):
    title: str
    shared_at: datetime
    messages: list[SharedMessage]


# ---------------------------------------------------------------- usage
class DailyCount(BaseModel):
    date: str
    count: int


class ImportCounts(BaseModel):
    succeeded: int
    failed: int
    active: int


class UsageLimits(BaseModel):
    questions_per_minute: int
    max_upload_mb: int
    max_document_chars: int
    max_active_imports: int


class UsageOut(BaseModel):
    documents: int
    chunks: int
    characters: int
    collections: int
    conversations: int
    questions: int
    answers: int
    refused_answers: int
    feedback_up: int
    feedback_down: int
    imports: ImportCounts
    daily_questions: list[DailyCount]
    limits: UsageLimits

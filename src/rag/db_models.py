from datetime import datetime
from typing import Any
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Hash to ensure idempotent ingestion
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    metadata_col: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    
    # The actual text
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # The vector (e.g., 1536 for OpenAI text-embedding-3-small)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    
    # Metadata for filtering (e.g., chunk index, page number)
    metadata_col: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    document: Mapped["Document"] = relationship(back_populates="chunks")

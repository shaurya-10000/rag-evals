import hashlib
import re
from typing import Any


class DocumentChunker:
    """Splits text into chunks, preserving words and sentence boundaries."""

    def __init__(self, chunk_size: int = 1000, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[str]:
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Split by sentence boundaries (approximate)
        sentences = re.split(r"(?<=[.!?]) +", text)

        chunks = []
        current_chunk = []
        current_length = 0

        for sentence in sentences:
            if current_length + len(sentence) <= self.chunk_size:
                current_chunk.append(sentence)
                current_length += len(sentence) + 1
            else:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_length = len(sentence)

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks


class IngestionPipeline:
    def __init__(self, chunker: DocumentChunker):
        self.chunker = chunker

    @staticmethod
    def compute_hash(text: str) -> str:
        """Compute SHA-256 hash to ensure idempotency."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def process_document(
        self, title: str, text: str, source_url: str | None = None
    ) -> dict[str, Any]:
        content_hash = self.compute_hash(text)
        chunks = self.chunker.split(text)
        chunk_data = [
            {"content": chunk, "metadata": {"index": i}} for i, chunk in enumerate(chunks)
        ]
        return {
            "title": title,
            "source_url": source_url,
            "content_hash": content_hash,
            "chunks": chunk_data,
        }

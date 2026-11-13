import hashlib
from typing import Any

class DocumentChunker:
    """Splits text into chunks. Pluggable for ablations later."""
    def __init__(self, chunk_size: int = 1000, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[str]:
        chunks = []
        for i in range(0, len(text), self.chunk_size - self.overlap):
            chunks.append(text[i:i + self.chunk_size])
        return chunks


class IngestionPipeline:
    def __init__(self, chunker: DocumentChunker):
        self.chunker = chunker

    @staticmethod
    def compute_hash(text: str) -> str:
        """Compute SHA-256 hash to ensure idempotency."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def process_document(self, title: str, text: str, source_url: str | None = None) -> dict[str, Any]:
        content_hash = self.compute_hash(text)
        chunks = self.chunker.split(text)
        chunk_data = [
            {"content": chunk, "metadata": {"index": i}} 
            for i, chunk in enumerate(chunks)
        ]
        return {
            "title": title,
            "source_url": source_url,
            "content_hash": content_hash,
            "chunks": chunk_data
        }

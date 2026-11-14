import uuid

from sqlalchemy.orm import Session

from rag.db_models import Chunk, Document
from rag.ingest.pipeline import DocumentChunker, IngestionPipeline
from rag.retrieve.embedder import Embedder


class DocumentRepository:
    def __init__(self, db: Session, embedder: Embedder):
        self.db = db
        self.embedder = embedder
        self.chunker = DocumentChunker(chunk_size=500, overlap=50)

    def ingest_document(
        self,
        user_id: uuid.UUID,
        title: str,
        text: str,
        source_url: str | None = None,
    ) -> Document:
        pipeline = IngestionPipeline(chunker=self.chunker)
        data = pipeline.process_document(title, text, source_url)
        content_hash = data["content_hash"]

        existing = (
            self.db.query(Document)
            .filter(Document.content_hash == content_hash, Document.user_id == user_id)
            .first()
        )
        if existing:
            return existing

        doc = Document(
            user_id=user_id,
            title=title,
            source_url=source_url,
            content_hash=content_hash,
        )
        self.db.add(doc)
        self.db.flush()

        chunks_data = data["chunks"]
        chunks_text = [c["content"] for c in chunks_data]
        embeddings = self.embedder.embed_texts(chunks_text)

        for chunk_info, embedding in zip(chunks_data, embeddings, strict=True):
            chunk = Chunk(
                document_id=doc.id,
                content=chunk_info["content"],
                embedding=embedding,
                metadata_col=chunk_info["metadata"],
            )
            self.db.add(chunk)

        self.db.commit()
        self.db.refresh(doc)
        return doc

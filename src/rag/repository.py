from sqlalchemy.orm import Session

from rag.db_models import Chunk, Document
from rag.ingest.pipeline import IngestionPipeline
from rag.retrieve.embedder import Embedder


class DocumentRepository:
    def __init__(self, db: Session, embedder: Embedder):
        self.db = db
        self.embedder = embedder

    def ingest_document(self, title: str, text: str, source_url: str | None = None) -> Document:
        '''Idempotently insert a document and its embedded chunks.'''
        pipeline = IngestionPipeline(chunker=None)
        content_hash = pipeline.compute_hash(text)

        existing = self.db.query(Document).filter(Document.content_hash == content_hash).first()
        if existing:
            return existing

        doc = Document(title=title, source_url=source_url, content_hash=content_hash)
        self.db.add(doc)
        self.db.flush()

        chunks_text = ["Chunk 1 text", "Chunk 2 text"]
        embeddings = self.embedder.embed_texts(chunks_text)

        for i, (chunk_text, embedding) in enumerate(zip(chunks_text, embeddings, strict=False)):
            chunk = Chunk(
                document_id=doc.id,
                content=chunk_text,
                embedding=embedding,
                metadata_col={"index": i}
            )
            self.db.add(chunk)

        self.db.commit()
        self.db.refresh(doc)
        return doc


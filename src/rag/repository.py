import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rag.db_models import Chunk, Collection, Document
from rag.ingest.pipeline import DEFAULT_CHUNK_SIZE, DocumentChunker, IngestionPipeline
from rag.retrieve.embedder import Embedder

EMBED_BATCH_SIZE = 50  # the embedding API caps how many texts one call may carry

ProgressCallback = Callable[[int, int], None]


class DuplicateDocumentError(Exception):
    """The user already has a document with identical content."""


class DuplicateCollectionError(Exception):
    """The user already has a collection with this name."""


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class DocumentRepository:
    def __init__(self, db: Session, embedder: Embedder):
        self.db = db
        self.embedder = embedder
        self.chunker = DocumentChunker(chunk_size=DEFAULT_CHUNK_SIZE)

    # ------------------------------------------------------------ ingest
    def find_existing(self, user_id: uuid.UUID, text: str) -> Document | None:
        """The user's document with identical text, if it was already ingested."""
        content_hash = IngestionPipeline.compute_hash(text)
        return (
            self.db.query(Document)
            .filter(Document.content_hash == content_hash, Document.user_id == user_id)
            .first()
        )

    def _embed_in_batches(
        self, texts: list[str], on_progress: ProgressCallback | None = None
    ) -> list[list[float]]:
        """Embed in small batches: the API caps texts per call, and progress needs steps."""
        total = len(texts)
        embeddings: list[list[float]] = []
        if on_progress is not None:
            on_progress(0, total)
        for start in range(0, total, EMBED_BATCH_SIZE):
            embeddings.extend(self.embedder.embed_texts(texts[start : start + EMBED_BATCH_SIZE]))
            if on_progress is not None:
                on_progress(len(embeddings), total)
        return embeddings

    def ingest_document(
        self,
        user_id: uuid.UUID,
        title: str,
        text: str,
        source_url: str | None = None,
        collection_id: uuid.UUID | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> Document:
        data = IngestionPipeline(chunker=self.chunker).process_document(title, text, source_url)

        existing = self.find_existing(user_id, text)
        if existing:
            return existing
        # Release the read transaction: embedding can take a while and needs no DB connection.
        self.db.commit()

        chunks_data = data["chunks"]
        embeddings = self._embed_in_batches([c["content"] for c in chunks_data], on_progress)

        doc = Document(
            user_id=user_id,
            collection_id=collection_id,
            title=title,
            source_url=source_url,
            content=text,
            content_hash=data["content_hash"],
        )
        try:
            self.db.add(doc)
            self.db.flush()
            for chunk_info, embedding in zip(chunks_data, embeddings, strict=True):
                self.db.add(
                    Chunk(
                        document_id=doc.id,
                        content=chunk_info["content"],
                        embedding=embedding,
                        metadata_col=chunk_info["metadata"],
                    )
                )
            self.db.commit()
        except IntegrityError:
            # A concurrent request ingested the same text first.
            self.db.rollback()
            raced = self.find_existing(user_id, text)
            if raced is None:
                raise
            return raced

        self.db.refresh(doc)
        return doc

    # --------------------------------------------------------- documents
    def list_documents(
        self,
        user_id: uuid.UUID,
        collection_id: uuid.UUID | None = None,
        unfiled: bool = False,
        search: str | None = None,
    ) -> list[Document]:
        q = self.db.query(Document).filter(Document.user_id == user_id)
        if unfiled:
            q = q.filter(Document.collection_id.is_(None))
        elif collection_id:
            q = q.filter(Document.collection_id == collection_id)
        if search and search.strip():
            pattern = f"%{_escape_like(search.strip())}%"
            q = q.filter(Document.title.ilike(pattern, escape="\\"))
        return q.order_by(Document.updated_at.desc()).all()

    def chunk_counts(self, doc_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not doc_ids:
            return {}
        rows = (
            self.db.query(Chunk.document_id, func.count(Chunk.id))
            .filter(Chunk.document_id.in_(doc_ids))
            .group_by(Chunk.document_id)
            .all()
        )
        return {doc_id: int(n) for doc_id, n in rows}

    def get_document(self, user_id: uuid.UUID, doc_id: uuid.UUID) -> Document | None:
        return (
            self.db.query(Document)
            .filter(Document.id == doc_id, Document.user_id == user_id)
            .first()
        )

    def get_content(self, doc: Document) -> str:
        """Return the stored text; lazily rebuild it from chunks for pre-feature documents."""
        if doc.content is not None:
            return doc.content
        ordered = sorted(doc.chunks, key=lambda c: int(c.metadata_col.get("index", 0)))
        text = " ".join(c.content for c in ordered)
        self.db.query(Document).filter(Document.id == doc.id).update(
            {"content": text, "updated_at": doc.updated_at}, synchronize_session=False
        )
        self.db.commit()
        self.db.refresh(doc)
        return text

    def rename_document(self, user_id: uuid.UUID, doc_id: uuid.UUID, title: str) -> Document | None:
        doc = self.get_document(user_id, doc_id)
        if doc is None:
            return None
        doc.title = title
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def update_content(self, user_id: uuid.UUID, doc_id: uuid.UUID, text: str) -> Document | None:
        """Replace a document's text: re-chunk, re-embed, swap chunks atomically."""
        doc = self.get_document(user_id, doc_id)
        if doc is None:
            return None

        pipeline = IngestionPipeline(chunker=self.chunker)
        data = pipeline.process_document(doc.title, text, doc.source_url)
        new_hash = data["content_hash"]

        if new_hash == doc.content_hash:
            if doc.content != text:
                doc.content = text
                self.db.commit()
                self.db.refresh(doc)
            return doc

        clash = (
            self.db.query(Document.id)
            .filter(
                Document.user_id == user_id,
                Document.content_hash == new_hash,
                Document.id != doc.id,
            )
            .first()
        )
        if clash:
            raise DuplicateDocumentError

        chunks_data = data["chunks"]
        # Embed BEFORE deleting anything, so an API failure leaves the old chunks intact.
        embeddings = self._embed_in_batches([c["content"] for c in chunks_data])

        try:
            self.db.query(Chunk).filter(Chunk.document_id == doc.id).delete(
                synchronize_session=False
            )
            for chunk_info, embedding in zip(chunks_data, embeddings, strict=True):
                self.db.add(
                    Chunk(
                        document_id=doc.id,
                        content=chunk_info["content"],
                        embedding=embedding,
                        metadata_col=chunk_info["metadata"],
                    )
                )
            doc.content = text
            doc.content_hash = new_hash
            doc.updated_at = datetime.now(UTC)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise DuplicateDocumentError from None
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(doc)
        return doc

    def move_document(
        self, user_id: uuid.UUID, doc_id: uuid.UUID, collection_id: uuid.UUID | None
    ) -> Document | None:
        doc = self.get_document(user_id, doc_id)
        if doc is None:
            return None
        doc.collection_id = collection_id
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def delete_document(self, user_id: uuid.UUID, doc_id: uuid.UUID) -> bool:
        doc = self.get_document(user_id, doc_id)
        if doc is None:
            return False
        self.db.delete(doc)
        self.db.commit()
        return True

    # -------------------------------------------------------- collections
    def list_collections(self, user_id: uuid.UUID) -> list[tuple[Collection, int]]:
        rows = (
            self.db.query(Collection, func.count(Document.id))
            .outerjoin(Document, Document.collection_id == Collection.id)
            .filter(Collection.user_id == user_id)
            .group_by(Collection.id)
            .order_by(func.lower(Collection.name))
            .all()
        )
        return [(col, int(n)) for col, n in rows]

    def get_collection(self, user_id: uuid.UUID, collection_id: uuid.UUID) -> Collection | None:
        return (
            self.db.query(Collection)
            .filter(Collection.id == collection_id, Collection.user_id == user_id)
            .first()
        )

    def collection_document_count(self, collection_id: uuid.UUID) -> int:
        return int(
            self.db.query(func.count(Document.id))
            .filter(Document.collection_id == collection_id)
            .scalar()
            or 0
        )

    def _name_taken(self, user_id: uuid.UUID, name: str, exclude: uuid.UUID | None) -> bool:
        q = self.db.query(Collection.id).filter(
            Collection.user_id == user_id, func.lower(Collection.name) == name.lower()
        )
        if exclude:
            q = q.filter(Collection.id != exclude)
        return q.first() is not None

    def create_collection(self, user_id: uuid.UUID, name: str) -> Collection:
        name = name.strip()
        if self._name_taken(user_id, name, None):
            raise DuplicateCollectionError
        col = Collection(user_id=user_id, name=name)
        self.db.add(col)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise DuplicateCollectionError from None
        self.db.refresh(col)
        return col

    def rename_collection(
        self, user_id: uuid.UUID, collection_id: uuid.UUID, name: str
    ) -> Collection | None:
        col = self.get_collection(user_id, collection_id)
        if col is None:
            return None
        name = name.strip()
        if self._name_taken(user_id, name, col.id):
            raise DuplicateCollectionError
        col.name = name
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise DuplicateCollectionError from None
        self.db.refresh(col)
        return col

    def delete_collection(
        self, user_id: uuid.UUID, collection_id: uuid.UUID, delete_documents: bool = False
    ) -> bool:
        col = self.get_collection(user_id, collection_id)
        if col is None:
            return False
        if delete_documents:
            for doc in list(col.documents):
                self.db.delete(doc)
        self.db.delete(col)
        self.db.commit()
        return True

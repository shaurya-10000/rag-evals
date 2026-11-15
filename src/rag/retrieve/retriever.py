import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from rag.db_models import Chunk, Document
from rag.retrieve.embedder import Embedder

RRF_K = 60
CANDIDATES_PER_SEARCH = 20


def reciprocal_rank_fusion(rankings: list[list[Chunk]], k: int = RRF_K) -> list[Chunk]:
    """Fuse ranked lists: each appearance adds 1 / (rank + k). Ties keep first-seen order."""
    scores: dict[uuid.UUID, float] = {}
    chunk_map: dict[uuid.UUID, Chunk] = {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking):
            chunk_map[chunk.id] = chunk
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (rank + k)
    ordered_ids = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
    return [chunk_map[chunk_id] for chunk_id in ordered_ids]


class Retriever:
    def __init__(self, db: Session, embedder: Embedder):
        self.db = db
        self.embedder = embedder

    def _vector_search(
        self,
        query_embedding: list[float],
        user_id: uuid.UUID | None,
        collection_id: uuid.UUID | None = None,
    ) -> list[Chunk]:
        q = self.db.query(Chunk).join(Document).filter(Chunk.embedding.isnot(None))
        if user_id:
            q = q.filter(Document.user_id == user_id)
        if collection_id:
            q = q.filter(Document.collection_id == collection_id)
        return (
            q.order_by(Chunk.embedding.cosine_distance(query_embedding))
            .limit(CANDIDATES_PER_SEARCH)
            .all()
        )

    def _keyword_search(
        self,
        query: str,
        user_id: uuid.UUID | None,
        collection_id: uuid.UUID | None = None,
    ) -> list[Chunk]:
        sql = (
            "SELECT c.id FROM chunks c "
            "JOIN documents d ON c.document_id = d.id "
            "WHERE c.search_vector IS NOT NULL "
            "AND c.search_vector @@ plainto_tsquery('english', :query)"
        )
        params: dict[str, str] = {"query": query}
        if user_id:
            sql += " AND d.user_id = :user_id"
            params["user_id"] = str(user_id)
        if collection_id:
            sql += " AND d.collection_id = :collection_id"
            params["collection_id"] = str(collection_id)
        sql += (
            " ORDER BY ts_rank(c.search_vector, plainto_tsquery('english', :query)) DESC"
            f" LIMIT {CANDIDATES_PER_SEARCH}"
        )

        keyword_ids = [row[0] for row in self.db.execute(text(sql), params).fetchall()]
        if not keyword_ids:
            return []

        # IN (...) returns rows in arbitrary order, so restore the ts_rank order.
        rows = self.db.query(Chunk).filter(Chunk.id.in_(keyword_ids)).all()
        by_id = {chunk.id: chunk for chunk in rows}
        return [by_id[chunk_id] for chunk_id in keyword_ids if chunk_id in by_id]

    def search(
        self,
        query: str,
        user_id: uuid.UUID | None = None,
        top_k: int = 5,
        collection_id: uuid.UUID | None = None,
    ) -> list[Chunk]:
        query_embedding = self.embedder.embed_text(query)
        vector_results = self._vector_search(query_embedding, user_id, collection_id)
        keyword_results = self._keyword_search(query, user_id, collection_id)
        return reciprocal_rank_fusion([vector_results, keyword_results])[:top_k]

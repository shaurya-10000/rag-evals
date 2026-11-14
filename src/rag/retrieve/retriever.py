import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from rag.db_models import Chunk, Document
from rag.retrieve.embedder import Embedder


class Retriever:
    def __init__(self, db: Session, embedder: Embedder):
        self.db = db
        self.embedder = embedder

    def search(self, query: str, user_id: uuid.UUID | None = None, top_k: int = 5) -> list[Chunk]:
        query_embedding = self.embedder.embed_text(query)

        vector_query = self.db.query(Chunk).join(Document).filter(Chunk.embedding.isnot(None))
        if user_id:
            vector_query = vector_query.filter(Document.user_id == user_id)

        vector_results = (
            vector_query.order_by(Chunk.embedding.cosine_distance(query_embedding)).limit(20).all()
        )

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

        sql += (
            " ORDER BY ts_rank(c.search_vector, plainto_tsquery('english', :query)) DESC LIMIT 20"
        )

        keyword_rows = self.db.execute(text(sql), params).fetchall()
        keyword_ids = [row[0] for row in keyword_rows]

        keyword_results = (
            (self.db.query(Chunk).filter(Chunk.id.in_(keyword_ids)).all()) if keyword_ids else []
        )

        k = 60
        rrf_scores: dict[uuid.UUID, float] = {}
        chunk_map: dict[uuid.UUID, Chunk] = {}

        for rank, chunk in enumerate(vector_results):
            chunk_map[chunk.id] = chunk
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + (1.0 / (rank + k))

        for rank, chunk in enumerate(keyword_results):
            chunk_map[chunk.id] = chunk
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + (1.0 / (rank + k))

        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        return [chunk_map[chunk_id] for chunk_id in sorted_ids[:top_k]]

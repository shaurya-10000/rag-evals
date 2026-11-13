import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from rag.db_models import Chunk
from rag.retrieve.embedder import Embedder


class Retriever:
    def __init__(self, db: Session, embedder: Embedder):
        self.db = db
        self.embedder = embedder

    def search(self, query: str, top_k: int = 5) -> list[Chunk]:
        '''Perform Hybrid Search (Vector + BM25) using Reciprocal Rank Fusion.'''
        
        # 1. Embed the query for vector search
        query_embedding = self.embedder.embed_text(query)
        
        # 2. Vector Search (Dense) - fetch top 20 candidates
        vector_query = (
            self.db.query(Chunk)
            .filter(Chunk.embedding.isnot(None))
            .order_by(Chunk.embedding.cosine_distance(query_embedding))
            .limit(20)
        )
        vector_results = vector_query.all()
        
        # 3. Keyword Search (BM25) - fetch top 20 candidates
        keyword_sql = text(
            "SELECT id FROM chunks "
            "WHERE search_vector IS NOT NULL "
            "AND search_vector @@ plainto_tsquery('english', :query) "
            "ORDER BY ts_rank(search_vector, plainto_tsquery('english', :query)) DESC "
            "LIMIT 20"
        )
        keyword_rows = self.db.execute(keyword_sql, {"query": query}).fetchall()
        keyword_ids = [row[0] for row in keyword_rows]
        
        # Fetch full chunk objects for the keyword results
        keyword_results = (
            self.db.query(Chunk)
            .filter(Chunk.id.in_(keyword_ids))
            .all()
        ) if keyword_ids else []

        # 4. Reciprocal Rank Fusion (RRF)
        k = 60
        rrf_scores: dict[uuid.UUID, float] = {}
        chunk_map = {}

        for rank, chunk in enumerate(vector_results):
            chunk_map[chunk.id] = chunk
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + (1.0 / (rank + k))

        for rank, chunk in enumerate(keyword_results):
            chunk_map[chunk.id] = chunk
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + (1.0 / (rank + k))

        # 5. Sort by RRF score and return the top_k
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        
        return [chunk_map[chunk_id] for chunk_id in sorted_ids[:top_k]]

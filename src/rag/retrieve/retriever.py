from sqlalchemy.orm import Session

from rag.db_models import Chunk
from rag.retrieve.embedder import Embedder


class Retriever:
    def __init__(self, db: Session, embedder: Embedder):
        self.db = db
        self.embedder = embedder

    def search(self, query: str, top_k: int = 5) -> list[Chunk]:
        '''Retrieve the top_k most similar chunks for a given query.'''
        # 1. Embed the query
        query_embedding = self.embedder.embed_text(query)

        # 2. Query the database using pgvector's cosine distance operator (<=>)
        # The smaller the distance, the more similar the chunk.
        results = (
            self.db.query(Chunk)
            .filter(Chunk.embedding.isnot(None))
            .order_by(Chunk.embedding.cosine_distance(query_embedding))
            .limit(top_k)
            .all()
        )
        return results

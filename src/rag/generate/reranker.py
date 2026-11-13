from sentence_transformers import CrossEncoder

from rag.db_models import Chunk


class Reranker:
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        mock: bool = False,
    ):
        self.mock = mock
        if not mock:
            self.model = CrossEncoder(model_name)

    def rerank(self, query: str, chunks: list[Chunk], top_k: int = 3) -> list[Chunk]:
        '''Rerank a list of chunks based on their actual relevance to the query.'''
        if self.mock or not chunks:
            return chunks[:top_k]

        # Create pairs of (query, chunk_content)
        pairs = [[query, chunk.content] for chunk in chunks]

        # Get relevance scores
        scores = self.model.predict(pairs)

        # Combine chunks with scores and sort descending
        scored_chunks = list(zip(chunks, scores, strict=False))
        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        # Return the top_k
        return [chunk for chunk, score in scored_chunks[:top_k]]

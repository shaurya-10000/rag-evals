from sentence_transformers import CrossEncoder

from rag.db_models import Chunk


class Reranker:
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        mock: bool = False,
    ):
        self.mock = mock
        self.model_name = model_name
        self._model = None  # <--- LAZY LOADING: Do not load on startup

    def _get_model(self):
        if self._model is None:
            # device='cpu' ensures we don't try to load GPU drivers (saves memory)
            self._model = CrossEncoder(self.model_name, device="cpu")
        return self._model

    def rerank(self, query: str, chunks: list[Chunk], top_k: int = 3) -> list[Chunk]:
        if self.mock or not chunks:
            return chunks[:top_k]

        model = self._get_model()
        pairs = [[query, chunk.content] for chunk in chunks]
        scores = model.predict(pairs)

        scored_chunks = list(zip(chunks, scores, strict=False))
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return [chunk for chunk, score in scored_chunks[:top_k]]

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from rag.db_models import Chunk

if TYPE_CHECKING:
    from fastembed.rerank.cross_encoder import TextCrossEncoder

DEFAULT_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"


class Reranker:
    def __init__(self, model_name: str = DEFAULT_MODEL, mock: bool = False) -> None:
        self.mock = mock
        self.model_name = model_name
        self._model: TextCrossEncoder | None = None

    def _get_model(self) -> TextCrossEncoder:
        if self._model is None:
            # Imported lazily so the API boots fast and tests with mock=True never load it.
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            self._model = TextCrossEncoder(
                model_name=self.model_name,
                cache_dir=os.getenv("FASTEMBED_CACHE_PATH"),
                threads=int(os.getenv("RERANK_THREADS", "1")),
            )
        return self._model

    def rerank(self, query: str, chunks: list[Chunk], top_k: int = 3) -> list[Chunk]:
        if self.mock or not chunks:
            return chunks[:top_k]

        model = self._get_model()
        scores = list(model.rerank(query, [chunk.content for chunk in chunks]))
        ranked = sorted(zip(chunks, scores, strict=True), key=lambda pair: pair[1], reverse=True)
        return [chunk for chunk, _ in ranked[:top_k]]
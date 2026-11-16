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
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            # Cap ONNX threads (Windows / container CPU quotas); override: RERANK_THREADS
            env_threads = os.getenv("RERANK_THREADS")
            threads = int(env_threads) if env_threads else min(4, os.cpu_count() or 1)

            self._model = TextCrossEncoder(
                model_name=self.model_name,
                cache_dir=os.getenv("FASTEMBED_CACHE_PATH"),
                threads=threads,
            )
        return self._model

    def rerank_scored(
        self, query: str, chunks: list[Chunk], top_k: int = 3
    ) -> tuple[list[Chunk], float | None]:
        """Return the selected chunks and the best relevance score (None when unscored)."""
        if self.mock or not chunks:
            return chunks[:top_k], None

        model = self._get_model()
        scores = [float(s) for s in model.rerank(query, [chunk.content for chunk in chunks])]

        ranked = sorted(zip(chunks, scores, strict=True), key=lambda pair: pair[1], reverse=True)
        best_score = ranked[0][1]

        threshold = float(os.getenv("RERANK_SCORE_THRESHOLD", "0.0"))
        filtered = [chunk for chunk, score in ranked if score >= threshold]

        if not filtered:
            return [ranked[0][0]], best_score

        return filtered[:top_k], best_score

    def rerank(self, query: str, chunks: list[Chunk], top_k: int = 3) -> list[Chunk]:
        return self.rerank_scored(query, chunks, top_k)[0]

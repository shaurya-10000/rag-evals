from typing import Any

import pytest

from rag.db_models import Chunk
from rag.generate.reranker import Reranker


class FakeModel:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        return self.scores


def _reranker(scores: list[float]) -> Reranker:
    reranker = Reranker()
    fake: Any = FakeModel(scores)
    reranker._model = fake
    return reranker


def test_returns_best_score_and_ranked_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RERANK_SCORE_THRESHOLD", "0.0")
    chunks = [Chunk(content="a"), Chunk(content="b"), Chunk(content="c")]
    selected, best = _reranker([1.0, 4.0, -2.0]).rerank_scored("q", chunks, top_k=2)
    assert best == 4.0
    assert [c.content for c in selected] == ["b", "a"]


def test_keeps_top_chunk_when_all_below_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RERANK_SCORE_THRESHOLD", "0.0")
    chunks = [Chunk(content="a"), Chunk(content="b")]
    selected, best = _reranker([-9.0, -7.0]).rerank_scored("q", chunks, top_k=3)
    assert best == -7.0
    assert [c.content for c in selected] == ["b"]


def test_mock_reranker_has_no_score() -> None:
    chunks = [Chunk(content="a"), Chunk(content="b")]
    selected, best = Reranker(mock=True).rerank_scored("q", chunks, top_k=1)
    assert best is None
    assert len(selected) == 1

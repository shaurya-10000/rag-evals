import pytest

from rag.db_models import Chunk
from rag.generate.reranker import Reranker


class FakeModel:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        return list(self.scores)


def _reranker(scores: list[float]) -> Reranker:
    reranker = Reranker()
    reranker._model = FakeModel(scores)  # type: ignore[assignment]
    return reranker


def _chunks(*names: str) -> list[Chunk]:
    return [Chunk(content=n) for n in names]


def _contents(chunks: list[Chunk]) -> list[str]:
    return [c.content for c in chunks]


@pytest.fixture(autouse=True)
def _default_threshold(monkeypatch):
    monkeypatch.delenv("RERANK_SCORE_THRESHOLD", raising=False)


def test_orders_by_score_and_truncates_to_top_k():
    result = _reranker([0.1, 0.9, 0.5]).rerank("q", _chunks("a", "b", "c"), top_k=2)
    assert _contents(result) == ["b", "c"]


def test_threshold_filters_low_scores(monkeypatch):
    monkeypatch.setenv("RERANK_SCORE_THRESHOLD", "0.5")
    result = _reranker([0.9, 0.2, 0.6]).rerank("q", _chunks("a", "b", "c"), top_k=3)
    assert _contents(result) == ["a", "c"]


def test_falls_back_to_best_chunk_when_all_below_threshold():
    result = _reranker([-3.0, -1.0]).rerank("q", _chunks("a", "b"), top_k=3)
    assert _contents(result) == ["b"]


def test_empty_candidates_return_empty_without_loading_model():
    assert Reranker().rerank("q", []) == []


def test_mock_mode_returns_first_top_k():
    result = Reranker(mock=True).rerank("q", _chunks("a", "b", "c"), top_k=2)
    assert _contents(result) == ["a", "b"]

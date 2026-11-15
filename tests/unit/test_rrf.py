import uuid

from rag.db_models import Chunk
from rag.retrieve.retriever import reciprocal_rank_fusion


def _chunk(content: str) -> Chunk:
    return Chunk(id=uuid.uuid4(), content=content)


def _contents(chunks: list[Chunk]) -> list[str]:
    return [c.content for c in chunks]


def test_empty_input_returns_empty():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_single_ranking_keeps_order():
    a, b, c = _chunk("a"), _chunk("b"), _chunk("c")
    assert _contents(reciprocal_rank_fusion([[a, b, c]])) == ["a", "b", "c"]


def test_chunk_in_both_rankings_beats_single_list_chunks():
    x, y, z = _chunk("x"), _chunk("y"), _chunk("z")
    fused = reciprocal_rank_fusion([[x, y], [z, y]])
    assert _contents(fused) == ["y", "x", "z"]  # x and z tie, first-seen wins


def test_agreement_can_outrank_a_single_top_hit():
    a, b, c, d = _chunk("a"), _chunk("b"), _chunk("c"), _chunk("d")
    fused = reciprocal_rank_fusion([[a, b, c, d], [d]])
    assert fused[0].content == "d"


def test_duplicates_are_returned_once():
    a, b = _chunk("a"), _chunk("b")
    fused = reciprocal_rank_fusion([[a, b], [b, a]])
    assert len(fused) == 2

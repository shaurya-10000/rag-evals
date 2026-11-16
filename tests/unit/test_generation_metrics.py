from rag.eval.generation_metrics import (
    faithfulness_from_verdicts,
    parse_json,
    relevance_from_rating,
)


def test_faithfulness_is_fraction_of_supported_claims() -> None:
    verdicts = [
        {"claim": "a", "supported": True},
        {"claim": "b", "supported": False},
        {"claim": "c", "supported": True},
        {"claim": "d", "supported": True},
    ]
    assert faithfulness_from_verdicts(verdicts) == 0.75


def test_faithfulness_none_without_claims() -> None:
    assert faithfulness_from_verdicts([]) is None
    assert faithfulness_from_verdicts("nope") is None


def test_relevance_maps_rating_to_unit_range() -> None:
    assert relevance_from_rating(1) == 0.0
    assert relevance_from_rating(3) == 0.5
    assert relevance_from_rating(5) == 1.0
    assert relevance_from_rating(9) == 1.0


def test_relevance_rejects_non_numbers() -> None:
    assert relevance_from_rating("5") is None
    assert relevance_from_rating(True) is None


def test_parse_json_strips_code_fences() -> None:
    assert parse_json('```json\n{"rating": 4}\n```') == {"rating": 4}
    assert parse_json("not json") is None

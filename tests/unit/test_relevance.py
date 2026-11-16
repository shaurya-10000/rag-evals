import pytest

from rag.generate.relevance import DEFAULT_REFUSAL_MIN_SCORE, should_refuse


def test_missing_score_never_refuses() -> None:
    assert should_refuse(None, -5.0) is False


def test_low_score_refuses() -> None:
    assert should_refuse(-8.0, -5.0) is True


def test_score_at_threshold_is_answered() -> None:
    assert should_refuse(-5.0, -5.0) is False


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REFUSAL_MIN_SCORE", "2.0")
    assert should_refuse(1.0) is True


def test_bad_env_value_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REFUSAL_MIN_SCORE", "not-a-number")
    assert should_refuse(DEFAULT_REFUSAL_MIN_SCORE - 1) is True
    assert should_refuse(DEFAULT_REFUSAL_MIN_SCORE + 1) is False

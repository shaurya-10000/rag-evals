import pytest

from rag.generate.rewriter import HistoryMessage, QueryRewriter

HISTORY = [
    HistoryMessage(role="user", content="Tell me about the Acme Rocket"),
    HistoryMessage(role="assistant", content="The Acme Rocket launched in 2005."),
]


def test_no_history_returns_query_without_calling_model(monkeypatch: pytest.MonkeyPatch) -> None:
    rewriter = QueryRewriter(mock=False)

    def boom(prompt: str) -> str | None:
        raise AssertionError("model must not be called")

    monkeypatch.setattr(rewriter, "_generate", boom)
    assert rewriter.rewrite("What is the Acme Rocket?", []) == "What is the Acme Rocket?"


def test_mock_mode_returns_query() -> None:
    assert QueryRewriter(mock=True).rewrite("and its price?", HISTORY) == "and its price?"


def test_rewrites_follow_up(monkeypatch: pytest.MonkeyPatch) -> None:
    rewriter = QueryRewriter(mock=False)
    monkeypatch.setattr(rewriter, "_generate", lambda prompt: '"What is the Acme Rocket price?"\n')
    assert rewriter.rewrite("and its price?", HISTORY) == "What is the Acme Rocket price?"


def test_falls_back_when_model_returns_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    rewriter = QueryRewriter(mock=False)
    monkeypatch.setattr(rewriter, "_generate", lambda prompt: None)
    assert rewriter.rewrite("and its price?", HISTORY) == "and its price?"


def test_falls_back_on_oversized_output(monkeypatch: pytest.MonkeyPatch) -> None:
    rewriter = QueryRewriter(mock=False)
    monkeypatch.setattr(rewriter, "_generate", lambda prompt: "x" * 2000)
    assert rewriter.rewrite("and its price?", HISTORY) == "and its price?"


def test_prompt_contains_history_and_query() -> None:
    prompt = QueryRewriter._build_prompt("and its price?", HISTORY)
    assert "User: Tell me about the Acme Rocket" in prompt
    assert "Assistant: The Acme Rocket launched in 2005." in prompt
    assert "Latest question: and its price?" in prompt

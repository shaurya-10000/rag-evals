from rag.chat_repository import make_snippet
from rag.db_models import Message
from rag.share_repository import MAX_SNAPSHOT_MESSAGES, build_snapshot


def test_snippet_centres_on_the_match() -> None:
    text = "word " * 30 + "NEEDLE here" + " word" * 30
    snippet = make_snippet(text, "needle")
    assert "NEEDLE here" in snippet
    assert snippet.startswith("...")
    assert snippet.endswith("...")
    assert len(snippet) < len(text)


def test_short_text_is_returned_whole() -> None:
    assert make_snippet("find me please", "me") == "find me please"


def test_snapshot_keeps_only_public_fields() -> None:
    message = Message(
        role="assistant",
        content="Answer [1]",
        sources=[
            {
                "id": "chunk-1",
                "document_id": "doc-1",
                "document_title": "Handbook",
                "content": "Passage text",
                "metadata": {"index": 0},
            }
        ],
    )
    snapshot = build_snapshot([message])
    assert snapshot == [
        {
            "role": "assistant",
            "content": "Answer [1]",
            "sources": [{"document_title": "Handbook", "content": "Passage text"}],
        }
    ]
    assert "doc-1" not in str(snapshot)
    assert "chunk-1" not in str(snapshot)


def test_snapshot_is_capped_to_the_latest_messages() -> None:
    messages = [Message(role="user", content=f"m{i}", sources=[]) for i in range(600)]
    snapshot = build_snapshot(messages)
    assert len(snapshot) == MAX_SNAPSHOT_MESSAGES
    assert snapshot[-1]["content"] == "m599"

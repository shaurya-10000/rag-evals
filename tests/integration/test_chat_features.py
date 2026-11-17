import json
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from rag.api.deps import get_embedder, get_generator, get_reranker, get_rewriter
from rag.api.main import app
from rag.config.settings import settings
from rag.generate.generator import Generator
from rag.generate.reranker import Reranker
from rag.generate.rewriter import QueryRewriter
from rag.retrieve.embedder import Embedder

HEADERS = {"X-API-Key": settings.RAG_API_KEY}
TEXT = "The Acme Rocket launched in 2005 and is used for small satellite launches. " * 4


@pytest.fixture
def client() -> Iterator[TestClient]:
    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_embedder] = lambda: Embedder(mock=True)
    app.dependency_overrides[get_generator] = lambda: Generator(mock=True)
    app.dependency_overrides[get_reranker] = lambda: Reranker(mock=True)
    app.dependency_overrides[get_rewriter] = lambda: QueryRewriter(mock=True)
    yield TestClient(app)
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


def _ask(client: TestClient, conversation_id: str, question: str) -> dict:
    """Run a question through the stream and return its final 'done' event."""
    payload = {"query": question, "top_k": 2, "conversation_id": conversation_id}
    with client.stream("POST", "/query", json=payload, headers=HEADERS) as response:
        assert response.status_code == 200
        raw = "".join(response.iter_text())
    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    return next(event for event in events if event["type"] == "done")


def _chat_with_answer(client: TestClient, verified_login, question: str = "what launched in 2005"):
    verified_login(client)
    ingest = client.post("/ingest", json={"title": "Acme", "text": TEXT}, headers=HEADERS)
    assert ingest.status_code == 200, ingest.text
    conversation = client.post("/conversations", json={"title": "Acme chat"}, headers=HEADERS)
    conversation_id = conversation.json()["id"]
    done = _ask(client, conversation_id, question)
    return conversation_id, done["message_id"]


def _detail(client: TestClient, conversation_id: str) -> dict:
    response = client.get(f"/conversations/{conversation_id}", headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def _feedback_url(conversation_id: str, message_id: str) -> str:
    return f"/conversations/{conversation_id}/messages/{message_id}/feedback"


def test_answer_is_saved_and_reports_its_id(client, verified_login) -> None:
    conversation_id, message_id = _chat_with_answer(client, verified_login)
    assistant = [
        m for m in _detail(client, conversation_id)["messages"] if m["role"] == "assistant"
    ]
    assert [m["id"] for m in assistant] == [message_id]
    assert assistant[0]["refused"] is False
    assert assistant[0]["rewritten_query"] is None
    assert assistant[0]["feedback"] is None


def test_feedback_round_trip(client, verified_login) -> None:
    conversation_id, message_id = _chat_with_answer(client, verified_login)
    url = _feedback_url(conversation_id, message_id)

    down = client.put(url, json={"rating": -1, "comment": "  Wrong answer "}, headers=HEADERS)
    assert down.status_code == 200, down.text
    assert down.json() == {"message_id": message_id, "rating": -1, "comment": "Wrong answer"}

    saved = [m for m in _detail(client, conversation_id)["messages"] if m["id"] == message_id][0]
    assert saved["feedback"] == -1
    assert saved["feedback_comment"] == "Wrong answer"

    up = client.put(url, json={"rating": 1}, headers=HEADERS)
    assert up.json()["rating"] == 1
    assert up.json()["comment"] is None

    cleared = client.delete(url, headers=HEADERS)
    assert cleared.json()["rating"] is None


def test_feedback_validation_and_ownership(client, verified_login) -> None:
    conversation_id, message_id = _chat_with_answer(client, verified_login)
    user_message = [m for m in _detail(client, conversation_id)["messages"] if m["role"] == "user"][
        0
    ]

    rejected = client.put(
        _feedback_url(conversation_id, user_message["id"]), json={"rating": 1}, headers=HEADERS
    )
    assert rejected.status_code == 422
    bad_rating = client.put(
        _feedback_url(conversation_id, message_id), json={"rating": 5}, headers=HEADERS
    )
    assert bad_rating.status_code == 422

    other = TestClient(app)
    verified_login(other)
    stranger = other.put(
        _feedback_url(conversation_id, message_id), json={"rating": 1}, headers=HEADERS
    )
    assert stranger.status_code == 404


def test_search_finds_titles_and_message_text(client, verified_login) -> None:
    conversation_id, _ = _chat_with_answer(
        client, verified_login, question="tell me about the zephyr rocket"
    )

    by_text = client.get("/search/conversations", params={"q": "ZEPHYR"}, headers=HEADERS).json()
    assert [hit["id"] for hit in by_text] == [conversation_id]
    assert "zephyr" in by_text[0]["snippet"].lower()

    by_title = client.get("/search/conversations", params={"q": "acme ch"}, headers=HEADERS).json()
    assert [hit["id"] for hit in by_title] == [conversation_id]

    nothing = client.get("/search/conversations", params={"q": "no-such-text"}, headers=HEADERS)
    assert nothing.json() == []

    other = TestClient(app)
    verified_login(other)
    assert other.get("/search/conversations", params={"q": "zephyr"}, headers=HEADERS).json() == []


def test_share_link_lifecycle(client, verified_login) -> None:
    conversation_id, _ = _chat_with_answer(client, verified_login)
    anonymous = TestClient(app)  # no session: only the API key, like the public page

    assert client.get(f"/conversations/{conversation_id}/share", headers=HEADERS).json() == {
        "shared": False,
        "token": None,
        "created_at": None,
        "updated_at": None,
    }

    created = client.post(f"/conversations/{conversation_id}/share", json={}, headers=HEADERS)
    assert created.status_code == 200, created.text
    token = created.json()["token"]
    assert created.json()["shared"] is True

    public = anonymous.get(f"/shared/{token}", headers=HEADERS)
    assert public.status_code == 200, public.text
    shared = public.json()
    assert shared["title"] == "Acme chat"
    assert [m["role"] for m in shared["messages"]] == ["user", "assistant"]
    assert shared["messages"][1]["sources"][0]["document_title"] == "Acme"
    assert "document_id" not in public.text

    _ask(client, conversation_id, "and who uses it")
    assert len(anonymous.get(f"/shared/{token}", headers=HEADERS).json()["messages"]) == 2

    updated = client.post(f"/conversations/{conversation_id}/share", json={}, headers=HEADERS)
    assert updated.json()["token"] == token
    assert len(anonymous.get(f"/shared/{token}", headers=HEADERS).json()["messages"]) == 4

    assert (
        client.delete(f"/conversations/{conversation_id}/share", headers=HEADERS).status_code == 200
    )
    assert anonymous.get(f"/shared/{token}", headers=HEADERS).status_code == 404
    assert (
        client.get(f"/conversations/{conversation_id}/share", headers=HEADERS).json()["shared"]
        is False
    )


def test_only_the_owner_can_share(client, verified_login) -> None:
    conversation_id, _ = _chat_with_answer(client, verified_login)
    other = TestClient(app)
    verified_login(other)
    stranger = other.post(f"/conversations/{conversation_id}/share", json={}, headers=HEADERS)
    assert stranger.status_code == 404


def test_unknown_share_token_is_a_404(client) -> None:
    assert TestClient(app).get("/shared/not-a-real-token", headers=HEADERS).status_code == 404


def test_usage_reflects_activity(client, verified_login) -> None:
    conversation_id, message_id = _chat_with_answer(client, verified_login)
    client.put(_feedback_url(conversation_id, message_id), json={"rating": 1}, headers=HEADERS)

    usage = client.get("/usage", headers=HEADERS)
    assert usage.status_code == 200, usage.text
    data = usage.json()
    assert data["documents"] == 1
    assert data["chunks"] >= 1
    assert data["conversations"] == 1
    assert data["questions"] == 1
    assert data["answers"] == 1
    assert data["refused_answers"] == 0
    assert data["feedback_up"] == 1
    assert data["feedback_down"] == 0
    assert len(data["daily_questions"]) == 14
    assert data["daily_questions"][-1] == {
        "date": datetime.now(UTC).date().isoformat(),
        "count": 1,
    }
    assert data["limits"]["max_upload_mb"] == 10

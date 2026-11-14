from fastapi.testclient import TestClient

from rag.api.main import app, get_generator, get_reranker
from rag.generate.generator import Generator
from rag.generate.reranker import Reranker

client = TestClient(app)

app.dependency_overrides[get_generator] = lambda: Generator(mock=True)
app.dependency_overrides[get_reranker] = lambda: Reranker(mock=True)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ingest_and_query():
    ingest_payload = {
        "title": "API Test Document",
        "text": "This is a unique document for the API test.",
        "source_url": "https://example.com",
    }
    response = client.post("/ingest", json=ingest_payload)
    assert response.status_code == 200

    query_payload = {"query": "unique document", "top_k": 2}
    response = client.post("/query", json=query_payload)
    assert response.status_code == 200
    
    # Verify it is a streaming response
    assert response.headers["content-type"].startswith("text/event-stream")
    
    # Parse the SSE stream
    raw_text = response.text
    assert "Mock" in raw_text
    assert "answer based on" in raw_text
    assert '"type": "sources"' in raw_text
    assert '"type": "done"' in raw_text

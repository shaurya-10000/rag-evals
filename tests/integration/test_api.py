from fastapi.testclient import TestClient

from rag.api.main import app, get_generator, get_reranker
from rag.generate.generator import Generator
from rag.generate.reranker import Reranker

client = TestClient(app)

# Override the generator dependency to use mock=True during testing
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
        "source_url": "https://example.com"
    }
    response = client.post("/ingest", json=ingest_payload)
    assert response.status_code == 200

    query_payload = {"query": "unique document", "top_k": 2}
    response = client.post("/query", json=query_payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "answer" in data
    assert "Mock answer based on" in data["answer"]
    assert len(data["results"]) > 0



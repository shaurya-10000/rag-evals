from fastapi.testclient import TestClient

from rag.api.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_ingest_and_query():
    # 1. Ingest a document
    ingest_payload = {
        "title": "API Test Document",
        "text": "This is a unique document for the API test.",
        "source_url": "https://example.com"
    }
    response = client.post("/ingest", json=ingest_payload)
    assert response.status_code == 200
    assert "document_id" in response.json()

    # 2. Query for it
    query_payload = {"query": "unique document", "top_k": 2}
    response = client.post("/query", json=query_payload)
    assert response.status_code == 200
    assert len(response.json()["results"]) > 0

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from rag.api.deps import get_embedder
from rag.api.main import app
from rag.config.settings import settings
from rag.ingest import jobs as jobs_module
from rag.ingest.extractors import ExtractionError
from rag.ingest.web import FetchedPage
from rag.retrieve.embedder import Embedder

HEADERS = {"X-API-Key": settings.RAG_API_KEY}
BODY = "Acme Corp was founded in 1995 in Seattle. The Acme Rocket launched in 2005. " * 12


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    app.dependency_overrides[get_embedder] = lambda: Embedder(mock=True)
    # Run jobs inline so tests do not have to wait on the worker pool.
    monkeypatch.setattr("rag.api.ingest_jobs.submit_job", jobs_module.run_ingest_job)
    yield TestClient(app)
    app.dependency_overrides.pop(get_embedder, None)


def _job(client: TestClient, job_id: str) -> dict:
    response = client.get(f"/ingest/jobs/{job_id}", headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def test_text_job_completes_with_progress(client, verified_login) -> None:
    verified_login(client)
    created = client.post("/ingest/jobs", json={"title": "Handbook", "text": BODY}, headers=HEADERS)
    assert created.status_code == 202, created.text
    assert created.json()["status"] == "queued"

    job = _job(client, created.json()["id"])
    assert job["status"] == "succeeded"
    assert job["stage"] == "done"
    assert job["document_id"]
    assert job["duplicate"] is False
    assert job["progress_total"] >= 1
    assert job["progress_done"] == job["progress_total"]


def test_same_text_is_reported_as_a_duplicate(client, verified_login) -> None:
    verified_login(client)
    first = client.post("/ingest/jobs", json={"text": BODY}, headers=HEADERS).json()
    second = client.post("/ingest/jobs", json={"text": BODY}, headers=HEADERS).json()

    first_done, second_done = _job(client, first["id"]), _job(client, second["id"])
    assert second_done["duplicate"] is True
    assert second_done["document_id"] == first_done["document_id"]


def test_csv_upload_job(client, verified_login) -> None:
    verified_login(client)
    files = {"file": ("people.csv", b"name,role\nAda,Engineer\nGrace,Admiral\n", "text/csv")}
    created = client.post("/ingest/jobs", files=files, data={"title": "People"}, headers=HEADERS)
    assert created.status_code == 202, created.text
    assert _job(client, created.json()["id"])["status"] == "succeeded"


def test_url_job_failure_is_reported(client, verified_login, monkeypatch) -> None:
    verified_login(client)

    def blocked(url: str) -> FetchedPage:
        raise ExtractionError("That address is not allowed.")

    monkeypatch.setattr("rag.ingest.jobs.fetch_url", blocked)
    created = client.post("/ingest/jobs", json={"url": "https://example.com/a"}, headers=HEADERS)
    job = _job(client, created.json()["id"])
    assert job["status"] == "failed"
    assert job["error"] == "That address is not allowed."


def test_url_job_uses_the_page_title(client, verified_login, monkeypatch) -> None:
    verified_login(client)
    page = FetchedPage(title="Phase Two Notes", text=BODY)
    monkeypatch.setattr("rag.ingest.jobs.fetch_url", lambda url: page)
    created = client.post("/ingest/jobs", json={"url": "https://example.com/a"}, headers=HEADERS)
    job = _job(client, created.json()["id"])
    assert job["status"] == "succeeded"
    assert job["title"] == "Phase Two Notes"


def test_bad_input_is_rejected(client, verified_login) -> None:
    verified_login(client)
    bad_url = client.post("/ingest/jobs", json={"url": "ftp://example.com"}, headers=HEADERS)
    assert bad_url.status_code == 422
    assert client.post("/ingest/jobs", json={"title": "x"}, headers=HEADERS).status_code == 422
    files = {"file": ("tool.exe", b"abc", "application/octet-stream")}
    assert client.post("/ingest/jobs", files=files, headers=HEADERS).status_code == 415


def test_jobs_are_private_to_their_owner(client, verified_login) -> None:
    verified_login(client)
    created = client.post("/ingest/jobs", json={"text": BODY}, headers=HEADERS).json()

    other = TestClient(app)
    verified_login(other)
    assert other.get(f"/ingest/jobs/{created['id']}", headers=HEADERS).status_code == 404
    assert created["id"] not in [j["id"] for j in other.get("/ingest/jobs", headers=HEADERS).json()]

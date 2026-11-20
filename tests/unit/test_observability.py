import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rag.auth.sessions import describe_device
from rag.observability import (
    REQUEST_ID_HEADER,
    JsonFormatter,
    RequestContextMiddleware,
    get_request_id,
)


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"request_id": get_request_id()}

    return app


def test_generates_and_echoes_a_request_id() -> None:
    response = TestClient(_app()).get("/ping")
    request_id = response.headers[REQUEST_ID_HEADER]
    assert request_id
    assert response.json()["request_id"] == request_id


def test_keeps_a_valid_incoming_id_and_replaces_junk() -> None:
    client = TestClient(_app())
    kept = client.get("/ping", headers={REQUEST_ID_HEADER: "abc12345-xyz"})
    assert kept.headers[REQUEST_ID_HEADER] == "abc12345-xyz"
    junk = client.get("/ping", headers={REQUEST_ID_HEADER: "x y"})
    assert junk.headers[REQUEST_ID_HEADER] != "x y"


def test_json_formatter_includes_structured_fields() -> None:
    record = logging.LogRecord("rag.test", logging.INFO, __file__, 1, "answer_complete", None, None)
    record.fields = {"timings_ms": {"total": 5}}
    data = json.loads(JsonFormatter().format(record))
    assert data["msg"] == "answer_complete"
    assert data["timings_ms"] == {"total": 5}


def test_describe_device() -> None:
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36"
    assert describe_device(ua) == "Chrome on Windows"
    assert describe_device(None) == "Unknown device"

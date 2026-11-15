import pytest
from google.genai import errors

from rag.retrieve.embedder import MAX_RETRY_DELAY, Embedder, _server_retry_delay


def _rate_limit_error(retry_delay: str | None) -> errors.APIError:
    details = []
    if retry_delay is not None:
        details.append(
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay}
        )
    body = {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED", "details": details}
    return errors.APIError(429, {"error": body})


class FailOnce:
    def __init__(self, error: errors.APIError) -> None:
        self.error = error
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.calls == 1:
            raise self.error
        return "ok"


@pytest.fixture
def sleeps(monkeypatch):
    recorded: list[float] = []
    monkeypatch.setattr("rag.retrieve.embedder.time.sleep", recorded.append)
    return recorded


def test_parses_retry_delay_from_error_details():
    assert _server_retry_delay(_rate_limit_error("16s")) == 16.0
    assert _server_retry_delay(_rate_limit_error("16.794324606s")) == pytest.approx(16.794324606)


def test_missing_or_malformed_delay_returns_none():
    assert _server_retry_delay(_rate_limit_error(None)) is None
    assert _server_retry_delay(_rate_limit_error("soon")) is None


def test_retry_waits_for_the_delay_the_server_asked_for(sleeps):
    call = FailOnce(_rate_limit_error("16s"))
    assert Embedder(mock=True)._with_retry(call) == "ok"
    assert sleeps == [16.5]


def test_server_delay_is_capped(sleeps):
    call = FailOnce(_rate_limit_error("120s"))
    assert Embedder(mock=True)._with_retry(call) == "ok"
    assert sleeps == [MAX_RETRY_DELAY]

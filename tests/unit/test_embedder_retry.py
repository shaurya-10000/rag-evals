import pytest
from google.genai import errors

from rag.retrieve.embedder import Embedder


def _api_error(code: int) -> errors.APIError:
    return errors.APIError(code, {"error": {"code": code, "message": "boom", "status": "ERR"}})


class Flaky:
    """Callable that raises the given API error codes in order, then succeeds."""

    def __init__(self, failure_codes: list[int]) -> None:
        self.failure_codes = list(failure_codes)
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.failure_codes:
            raise _api_error(self.failure_codes.pop(0))
        return "ok"


@pytest.fixture
def sleeps(monkeypatch):
    recorded: list[float] = []
    monkeypatch.setattr("rag.retrieve.embedder.time.sleep", recorded.append)
    return recorded


def test_success_needs_no_retry(sleeps):
    call = Flaky([])
    assert Embedder(mock=True)._with_retry(call) == "ok"
    assert call.calls == 1
    assert sleeps == []


def test_retries_transient_errors_with_exponential_backoff(sleeps):
    call = Flaky([503, 429])
    assert Embedder(mock=True, base_delay=1.0)._with_retry(call) == "ok"
    assert call.calls == 3
    assert sleeps == [1.0, 2.0]


def test_non_retryable_error_is_raised_immediately(sleeps):
    call = Flaky([400])
    with pytest.raises(errors.APIError):
        Embedder(mock=True)._with_retry(call)
    assert call.calls == 1
    assert sleeps == []


def test_gives_up_after_max_attempts(sleeps):
    call = Flaky([503] * 5)
    with pytest.raises(errors.APIError):
        Embedder(mock=True, max_attempts=3, base_delay=1.0)._with_retry(call)
    assert call.calls == 3
    assert sleeps == [1.0, 2.0]

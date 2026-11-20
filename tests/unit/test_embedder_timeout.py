import httpx
import pytest

from rag.retrieve.embedder import Embedder


@pytest.fixture
def sleeps(monkeypatch):
    recorded: list[float] = []
    monkeypatch.setattr("rag.retrieve.embedder.time.sleep", recorded.append)
    return recorded


class TimesOutOnce:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.calls == 1:
            raise httpx.ReadTimeout("timed out")
        return "ok"


def test_timeouts_are_retried(sleeps):
    call = TimesOutOnce()
    assert Embedder(mock=True, base_delay=1.0)._with_retry(call) == "ok"
    assert call.calls == 2
    assert sleeps == [1.0]


def test_timeouts_give_up_after_max_attempts(sleeps):
    def always_times_out() -> str:
        raise httpx.ReadTimeout("timed out")

    with pytest.raises(httpx.ReadTimeout):
        Embedder(mock=True, max_attempts=2, base_delay=1.0)._with_retry(always_times_out)
    assert sleeps == [1.0]

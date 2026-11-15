"""Record real Gemini embeddings for the eval gold set as a CI fixture.

Run from the repo root whenever the gold set or chunking settings change
(needs GEMINI_API_KEY), then commit the output:

    python -m rag.eval.generate_fixtures

Paces itself under the free-tier quota and resumes from a partial fixture.
"""

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from google.genai import errors

from rag.ingest.pipeline import DEFAULT_CHUNK_SIZE, DocumentChunker
from rag.retrieve.embedder import Embedder, fixture_key

T = TypeVar("T")

GOLD_SET = Path("eval/gold_set/qa_pairs.json")
OUTPUT = Path("eval/fixtures/embeddings.json")

# Must match DocumentRepository's chunker so document keys line up at eval time.

BATCH_SIZE = 20
PRECISION = 6

# Free tier allows 100 embed requests/minute (each text counts); stay under it.
REQUESTS_PER_WINDOW = 80
WINDOW_SECONDS = 60.0
QUOTA_COOLDOWN_SECONDS = 62.0
MAX_QUOTA_RETRIES = 6


class Throttle:
    """Sliding-window limiter: at most `limit` requests per `window` seconds."""

    def __init__(self, limit: int, window: float):
        self.limit = limit
        self.window = window
        self.events: list[tuple[float, int]] = []

    def acquire(self, n: int) -> None:
        while True:
            now = time.monotonic()
            self.events = [(t, c) for t, c in self.events if now - t < self.window]
            used = sum(c for _, c in self.events)
            if used + n <= self.limit:
                self.events.append((now, n))
                return
            wait = self.window - (now - self.events[0][0]) + 1
            print(f"  pacing: sleeping {wait:.0f}s to stay under quota")
            time.sleep(max(wait, 1.0))


def with_quota_retry(call: Callable[[], T]) -> T:
    for attempt in range(1, MAX_QUOTA_RETRIES + 1):
        try:
            return call()
        except errors.APIError as e:
            if e.code != 429 or attempt == MAX_QUOTA_RETRIES:
                raise
            print(
                f"  quota hit, cooling down {QUOTA_COOLDOWN_SECONDS:.0f}s "
                f"({attempt}/{MAX_QUOTA_RETRIES})"
            )
            time.sleep(QUOTA_COOLDOWN_SECONDS)
    raise RuntimeError("unreachable")  # pragma: no cover


def save(fixture: dict[str, list[float]]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(fixture, separators=(",", ":")), encoding="utf-8")


def main() -> None:
    gold = json.loads(GOLD_SET.read_text(encoding="utf-8"))
    items = [
        i for i in gold if i.get("expected_answer_chunk") and i["expected_answer_chunk"] != "NONE"
    ]

    chunker = DocumentChunker(chunk_size=DEFAULT_CHUNK_SIZE)
    doc_texts = sorted({c for i in items for c in chunker.split(i["expected_answer_chunk"])})
    queries = sorted({i["question"] for i in items})
    print(f"{len(items)} scored questions, {len(doc_texts)} unique chunks, {len(queries)} queries")

    fixture: dict[str, list[float]] = {}
    if OUTPUT.exists():
        fixture = json.loads(OUTPUT.read_text(encoding="utf-8-sig"))
        print(f"resuming with {len(fixture)} vectors already recorded")

    todo_docs = [t for t in doc_texts if fixture_key("doc", t) not in fixture]
    todo_queries = [q for q in queries if fixture_key("query", q) not in fixture]
    print(f"to embed: {len(todo_docs)} chunks, {len(todo_queries)} queries")

    embedder = Embedder(mock=False)
    throttle = Throttle(REQUESTS_PER_WINDOW, WINDOW_SECONDS)

    for start in range(0, len(todo_docs), BATCH_SIZE):
        batch = todo_docs[start : start + BATCH_SIZE]
        throttle.acquire(len(batch))
        vectors = with_quota_retry(lambda b=batch: embedder.embed_texts(b))  # type: ignore[misc]
        for text, vec in zip(batch, vectors, strict=True):
            fixture[fixture_key("doc", text)] = [round(v, PRECISION) for v in vec]
        save(fixture)
        print(f"embedded chunks {start + len(batch)}/{len(todo_docs)}")

    for n, query in enumerate(todo_queries, start=1):
        throttle.acquire(1)
        vec = with_quota_retry(lambda q=query: embedder.embed_text(q))  # type: ignore[misc]
        fixture[fixture_key("query", query)] = [round(v, PRECISION) for v in vec]
        if n % 5 == 0 or n == len(todo_queries):
            save(fixture)
        print(f"embedded queries {n}/{len(todo_queries)}")

    save(fixture)
    size_kb = OUTPUT.stat().st_size / 1024
    print(f"wrote {OUTPUT} ({len(fixture)} vectors, {size_kb:.0f} KB)")


if __name__ == "__main__":
    main()

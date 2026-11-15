import hashlib
import json
import logging
import os
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from google import genai
from google.genai import errors, types

from rag.config.settings import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Transient errors worth retrying: rate limit + server-side failures
RETRYABLE_CODES = {429, 500, 502, 503, 504}

EMBEDDING_DIM = 768

# <repo root>/eval/fixtures/embeddings.json (src/rag/retrieve/embedder.py -> parents[3])
DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[3] / "eval" / "fixtures" / "embeddings.json"


def fixture_key(kind: str, text: str) -> str:
    """Stable fixture key. `kind` is 'doc' (documents) or 'query' (search queries)."""
    return hashlib.sha256(f"{kind}:{text}".encode()).hexdigest()


MAX_RETRY_DELAY = 20.0  # never sleep longer than this between attempts (seconds)


def _server_retry_delay(error: errors.APIError) -> float | None:
    """Seconds the API asks us to wait (RetryInfo.retryDelay, e.g. "16s"), if present."""
    payload = getattr(error, "details", None)
    if not isinstance(payload, dict):
        return None
    inner = payload.get("error", payload)
    items = inner.get("details", []) if isinstance(inner, dict) else []
    for item in items:
        if isinstance(item, dict) and str(item.get("@type", "")).endswith("RetryInfo"):
            match = re.fullmatch(r"(\d+(?:\.\d+)?)s", str(item.get("retryDelay", "")))
            if match:
                return float(match.group(1))
    return None


class Embedder:
    def __init__(
        self,
        model: str = "gemini-embedding-001",
        mock: bool = False,
        max_attempts: int = 6,
        base_delay: float = 1.0,
        fixture_path: Path | None = None,
    ):
        self.model = model
        self.mock = mock
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self._fixture: dict[str, list[float]] = {}
        if mock:
            self._fixture = self._load_fixture(fixture_path)
        else:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    @staticmethod
    def _load_fixture(path: Path | None) -> dict[str, list[float]]:
        """Load pre-recorded real embeddings so mock mode behaves like production."""
        resolved = Path(path or os.environ.get("MOCK_EMBEDDINGS_PATH") or DEFAULT_FIXTURE_PATH)
        if not resolved.exists():
            logger.warning(
                "mock embedding fixture not found at %s; using hashed fallback vectors", resolved
            )
            return {}
        with resolved.open(encoding="utf-8-sig") as f:
            data: dict[str, list[float]] = json.load(f)
        return data

    def _with_retry(self, call: Callable[[], T]) -> T:
        """Run an API call, retrying transient failures with exponential backoff."""
        for attempt in range(1, self.max_attempts + 1):
            try:
                return call()
            except errors.APIError as e:
                retryable = e.code in RETRYABLE_CODES
                if not retryable or attempt == self.max_attempts:
                    raise
                delay = self.base_delay * (2 ** (attempt - 1))
                server_delay = _server_retry_delay(e)
                if server_delay is not None:
                    delay = min(max(delay, server_delay + 0.5), MAX_RETRY_DELAY)
                logger.warning(
                    "embedding failed code=%s attempt=%d/%d, retrying in %.1fs",
                    e.code,
                    attempt,
                    self.max_attempts,
                    delay,
                )
                time.sleep(delay)
        raise RuntimeError("unreachable")  # pragma: no cover

    def _generate_mock_vector(self, text: str, dim: int = EMBEDDING_DIM) -> list[float]:
        """Deterministic hashed bag-of-words vector: shared words => similar vectors."""
        vector = [0.0] * dim
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            digest = hashlib.md5(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[idx] += sign

        norm = sum(v * v for v in vector) ** 0.5
        if norm == 0:
            vector[0] = 1.0  # avoid zero vector for empty/no-token text
            return vector
        return [v / norm for v in vector]

    def _mock_vector(self, kind: str, text: str) -> list[float]:
        """Replay a recorded real embedding; fall back to the hashed vector on a miss."""
        vector = self._fixture.get(fixture_key(kind, text))
        if vector is not None:
            return vector
        logger.warning("mock fixture miss kind=%s text=%.60r; using hashed fallback", kind, text)
        return self._generate_mock_vector(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate document embeddings using Gemini."""
        if self.mock:
            return [self._mock_vector("doc", t) for t in texts]

        result = self._with_retry(
            lambda: self.client.models.embed_content(
                model=self.model,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=EMBEDDING_DIM,
                ),
            )
        )
        return [e.values for e in result.embeddings]

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a query."""
        if self.mock:
            return self._mock_vector("query", text)

        result = self._with_retry(
            lambda: self.client.models.embed_content(
                model=self.model,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_QUERY",
                    output_dimensionality=EMBEDDING_DIM,
                ),
            )
        )
        return result.embeddings[0].values

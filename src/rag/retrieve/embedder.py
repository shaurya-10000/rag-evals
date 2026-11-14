import logging
import time
from collections.abc import Callable
from typing import TypeVar

from google import genai
from google.genai import errors, types

from rag.config.settings import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Transient errors worth retrying: rate limit + server-side failures
RETRYABLE_CODES = {429, 500, 502, 503, 504}


class Embedder:
    def __init__(
        self,
        model: str = "gemini-embedding-001",
        mock: bool = False,
        max_attempts: int = 5,
        base_delay: float = 1.0,
    ):
        self.model = model
        self.mock = mock
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        if not mock:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

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
                logger.warning(
                    "embedding failed code=%s attempt=%d/%d, retrying in %.1fs",
                    e.code,
                    attempt,
                    self.max_attempts,
                    delay,
                )
                time.sleep(delay)
        raise RuntimeError("unreachable")  # pragma: no cover

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using Gemini."""
        if self.mock:
            return [[0.01] * 768 for _ in texts]

        result = self._with_retry(
            lambda: self.client.models.embed_content(
                model=self.model,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=768,
                ),
            )
        )
        return [e.values for e in result.embeddings]

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a query."""
        if self.mock:
            return [0.01] * 768

        result = self._with_retry(
            lambda: self.client.models.embed_content(
                model=self.model,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_QUERY",
                    output_dimensionality=768,
                ),
            )
        )
        return result.embeddings[0].values

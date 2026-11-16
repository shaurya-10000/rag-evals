"""Rewrite a follow-up question into a standalone search query using chat history."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from google import genai
from google.genai import types

from rag.config.settings import settings

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 6
MAX_HISTORY_MESSAGE_CHARS = 600
MAX_REWRITE_CHARS = 500
REWRITE_TIMEOUT_MS = 8000
REWRITE_MODELS = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]

REWRITE_PROMPT = """Rewrite the user's LATEST question as a standalone search query.
Resolve pronouns and vague references ("it", "that", "what about pricing?") using the
conversation. Keep names, numbers and technical terms exactly as written. If the latest
question is already standalone, return it unchanged. Output ONLY the rewritten query,
with no quotes and no explanation.

Conversation:
<<HISTORY>>

Latest question: <<QUERY>>
Standalone query:"""


@dataclass(frozen=True)
class HistoryMessage:
    role: str
    content: str


class QueryRewriter:
    def __init__(self, mock: bool = False, models: Sequence[str] = REWRITE_MODELS) -> None:
        self.mock = mock
        self.models = list(models)
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(
                api_key=settings.GEMINI_API_KEY,
                http_options=types.HttpOptions(timeout=REWRITE_TIMEOUT_MS),
            )
        return self._client

    @staticmethod
    def _build_prompt(query: str, history: Sequence[HistoryMessage]) -> str:
        lines = []
        for message in history[-MAX_HISTORY_MESSAGES:]:
            speaker = "User" if message.role == "user" else "Assistant"
            lines.append(f"{speaker}: {message.content[:MAX_HISTORY_MESSAGE_CHARS]}")
        return REWRITE_PROMPT.replace("<<HISTORY>>", "\n".join(lines)).replace("<<QUERY>>", query)

    @staticmethod
    def _clean(raw: str | None, fallback: str) -> str:
        if not raw:
            return fallback
        lines = [line.strip() for line in raw.strip().splitlines() if line.strip()]
        if not lines:
            return fallback
        candidate = lines[0].strip("`\"' ")
        if not candidate or len(candidate) > MAX_REWRITE_CHARS:
            return fallback
        return candidate

    def _generate(self, prompt: str) -> str | None:
        client = self._get_client()
        for model in self.models:
            try:
                response = client.models.generate_content(model=model, contents=prompt)
            except Exception as e:
                logger.warning("query rewrite failed model=%s error=%s", model, e)
                continue
            if response.text:
                return response.text
        return None

    def rewrite(self, query: str, history: Sequence[HistoryMessage]) -> str:
        """Return a standalone query. Falls back to the original on any problem."""
        if self.mock or not history:
            return query
        raw = self._generate(self._build_prompt(query, history))
        return self._clean(raw, fallback=query)

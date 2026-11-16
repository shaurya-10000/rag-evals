"""LLM-as-judge generation metrics (RAGAS-style): faithfulness and answer relevance.

Meant to be run locally. They cost several Gemini calls per question, so they are not
part of the CI gate.
"""

import json
import logging
from collections.abc import Sequence
from typing import Any

from google import genai
from google.genai import types

from rag.config.settings import settings

logger = logging.getLogger(__name__)

JUDGE_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
JUDGE_TIMEOUT_MS = 30000

FAITHFULNESS_PROMPT = """You are a strict fact-checker. Break the ANSWER into its individual
factual claims (ignore citation markers like [1] and formatting). For each claim decide
whether it is fully supported by the CONTEXT. Respond with JSON only, in this shape:
{"claims": [{"claim": "...", "supported": true}]}

CONTEXT:
<<CONTEXT>>

ANSWER:
<<ANSWER>>"""

RELEVANCE_PROMPT = """You are a strict evaluator. Rate from 1 to 5 how directly and completely
the ANSWER addresses the QUESTION (1 = off-topic or evasive, 5 = fully and directly answers).
Judge relevance only, not factual accuracy. Respond with JSON only: {"rating": <1-5>}

QUESTION:
<<QUESTION>>

ANSWER:
<<ANSWER>>"""


def parse_json(raw: str) -> Any | None:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return json.loads(text.strip())
    except ValueError:
        return None


def faithfulness_from_verdicts(verdicts: object) -> float | None:
    """Fraction of claims judged supported. None when no claims were extracted."""
    if not isinstance(verdicts, list) or not verdicts:
        return None
    supported = sum(1 for v in verdicts if isinstance(v, dict) and v.get("supported") is True)
    return supported / len(verdicts)


def relevance_from_rating(rating: object) -> float | None:
    """Map a 1-5 rating to 0-1. None for anything that is not a number."""
    if isinstance(rating, bool) or not isinstance(rating, int | float):
        return None
    clamped = min(5.0, max(1.0, float(rating)))
    return (clamped - 1.0) / 4.0


class LLMJudge:
    def __init__(self, models: Sequence[str] = JUDGE_MODELS) -> None:
        self.models = list(models)
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(
                api_key=settings.GEMINI_API_KEY,
                http_options=types.HttpOptions(timeout=JUDGE_TIMEOUT_MS),
            )
        return self._client

    def _ask_json(self, prompt: str) -> Any | None:
        client = self._get_client()
        for model in self.models:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json", temperature=0.0
                    ),
                )
            except Exception as e:
                logger.warning("judge call failed model=%s error=%s", model, e)
                continue
            parsed = parse_json(response.text or "")
            if parsed is not None:
                return parsed
        return None

    def faithfulness(self, answer: str, contexts: Sequence[str]) -> float | None:
        context = "\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(contexts))
        prompt = FAITHFULNESS_PROMPT.replace("<<CONTEXT>>", context).replace("<<ANSWER>>", answer)
        data = self._ask_json(prompt)
        return faithfulness_from_verdicts(data.get("claims") if isinstance(data, dict) else None)

    def answer_relevance(self, question: str, answer: str) -> float | None:
        prompt = RELEVANCE_PROMPT.replace("<<QUESTION>>", question).replace("<<ANSWER>>", answer)
        data = self._ask_json(prompt)
        return relevance_from_rating(data.get("rating") if isinstance(data, dict) else None)

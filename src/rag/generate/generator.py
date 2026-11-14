import logging
import time
from collections.abc import Generator as TypingGenerator

from google import genai
from google.genai import types

from rag.config.settings import settings
from rag.db_models import Chunk

logger = logging.getLogger(__name__)


class Generator:
    def __init__(self, mock: bool = False):
        self.mock = mock
        self.models = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash"]
        if not mock:
            self.client = genai.Client(
                api_key=settings.GEMINI_API_KEY,
                http_options=types.HttpOptions(timeout=15000),
            )

    def _build_prompt(self, query: str, chunks: list[Chunk]) -> str:
        context = ""
        for i, chunk in enumerate(chunks):
            context += f"[{i + 1}] {chunk.content}\n\n"

        return f"""You are a helpful assistant.
Answer the user's question using ONLY the provided context.
If the exact answer is not in the context, provide a helpful summary 
based on the context you do have, rather than saying 'I don't know'.
Cite the context chunks you use by writing [1], [2], etc.

Context:
{context}

Question: {query}
Answer:"""

    def generate_answer(self, query: str, chunks: list[Chunk]) -> str:
        if self.mock:
            return f"Mock answer based on {len(chunks)} chunks."

        if not chunks:
            return "I could not find any relevant info to answer your question."

        prompt = self._build_prompt(query, chunks)

        for model in self.models:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                if response.text:
                    return response.text
            except Exception as e:
                logger.warning(f"generation failed model={model} error={e}")
                continue

        return "Error: All LLM models are currently unavailable. Please try again later."

    def stream_answer(self, query: str, chunks: list[Chunk]) -> TypingGenerator[str, None, None]:
        if self.mock:
            yield "Mock "
            yield "streaming "
            yield f"answer based on {len(chunks)} chunks."
            return

        if not chunks:
            yield "I could not find any relevant info to answer your question."
            return

        prompt = self._build_prompt(query, chunks)

        for model in self.models:
            started = time.perf_counter()
            try:
                response = self.client.models.generate_content_stream(
                    model=model,
                    contents=prompt,
                )
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
                elapsed = time.perf_counter() - started
                logger.info(f"stream ok model={model} time={elapsed:.1f}s")
                return
            except Exception as e:
                elapsed = time.perf_counter() - started
                logger.warning(f"stream failed model={model} time={elapsed:.1f}s error={e}")
                continue

        yield "Error: All LLM models are currently unavailable. Please try again later."

import logging
import time

from google import genai
from google.genai import types

from rag.config.settings import settings
from rag.db_models import Chunk

logger = logging.getLogger(__name__)


class Generator:
    def __init__(self, mock: bool = False):
        self.mock = mock
        # Hierarchical fallback list (Best -> Fast -> Fallback)
        self.models = [
            "gemini-3.8-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.6-flash"
        ]
        if not mock:
            self.client = genai.Client(
                api_key=settings.GEMINI_API_KEY,
                http_options=types.HttpOptions(timeout=15000)
            )

    def generate_answer(self, query: str, chunks: list[Chunk]) -> str:
        '''Generate an answer using the retrieved chunks as context.'''
        if self.mock:
            return f"Mock answer based on {len(chunks)} chunks."

        if not chunks:
            return "I could not find any relevant info to answer your question."

        # 1. Build the context string with citations
        context = ""
        for i, chunk in enumerate(chunks):
            context += f"[{i+1}] {chunk.content}\n\n"

        # 2. Create the prompt
        prompt = f"""You are a helpful assistant.
Answer the user's question using ONLY the provided context.
If the answer is not in the context, say 'I don't know'.
Cite the context chunks you use by writing [1], [2], etc.

Context:
{context}

Question: {query}
Answer:"""

        # 3. Try models in order (Fallback pattern)
        for model in self.models:
            started = time.perf_counter()
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                elapsed = time.perf_counter() - started
                if response.text:
                    logger.info("generation ok model=%s time=%.1fs", model, elapsed)
                    return response.text
                logger.warning("generation empty model=%s time=%.1fs", model, elapsed)
            except Exception as e:
                # If it fails (503, 429, 404, timeout), log it and try the next model
                elapsed = time.perf_counter() - started
                logger.warning(
                    "generation failed model=%s time=%.1fs error=%s", model, elapsed, e
                )
                continue

        # If all models fail
        return "Error: All LLM models are currently unavailable. Please try again later."
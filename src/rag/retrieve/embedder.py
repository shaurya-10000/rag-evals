from google import genai
from google.genai import types

from rag.config.settings import settings


class Embedder:
    def __init__(self, model: str = "gemini-embedding-001", mock: bool = False):
        self.model = model
        self.mock = mock
        if not mock:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        '''Generate embeddings using Gemini.'''
        if self.mock:
            return [[0.01] * 768 for _ in texts]

        result = self.client.models.embed_content(
            model=self.model,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=768
            )
        )
        return [e.values for e in result.embeddings]

    def embed_text(self, text: str) -> list[float]:
        '''Generate embedding for a query.'''
        if self.mock:
            return [0.01] * 768
        
        result = self.client.models.embed_content(
            model=self.model,
            contents=text,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=768
            )
        )
        return result.embeddings[0].values

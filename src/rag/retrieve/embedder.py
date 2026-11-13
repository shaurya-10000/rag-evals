import openai

from rag.config.settings import settings


class Embedder:
    def __init__(self, model: str = "text-embedding-3-small", mock: bool = False):
        self.model = model
        self.mock = mock
        if not mock:
            self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        '''Generate embeddings for a list of texts.'''
        if self.mock:
            return [[0.01] * 1536 for _ in texts]
        
        response = self.client.embeddings.create(input=texts, model=self.model)
        return [data.embedding for data in response.data]

    def embed_text(self, text: str) -> list[float]:
        '''Generate embedding for a single string.'''
        return self.embed_texts([text])[0]

from google import genai

from rag.config.settings import settings
from rag.db_models import Chunk


class Generator:
    def __init__(self, model: str = "gemini-2.5-flash", mock: bool = False):
        self.model = model
        self.mock = mock
        if not mock:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

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

        # 3. Call Gemini
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        return response.text or "Error: No response generated."

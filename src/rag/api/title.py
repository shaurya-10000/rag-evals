import logging

from fastapi import APIRouter, Depends
from google import genai

from rag.api.deps import verify_api_key
from rag.api.schemas import TitleRequest
from rag.config.settings import settings

logger = logging.getLogger("rag.api.title")
router = APIRouter()

TITLE_MODEL = "gemini-3.5-flash-lite"


@router.post("/generate-title")
def generate_title(
    payload: TitleRequest,
    _: str = Depends(verify_api_key),
) -> dict[str, str]:
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        prompt = (
            "Summarize this prompt in 3 to 5 words to be used as a chat title. "
            "Do not use punctuation. Output ONLY the title.\n\n"
            f"Prompt: {payload.prompt}"
        )
        response = client.models.generate_content(model=TITLE_MODEL, contents=prompt)
        title = (response.text or "").strip().strip('"').strip("'")
        return {"title": title or "New Chat"}
    except Exception as e:
        logger.error(f"Title generation failed: {e}")
        return {"title": payload.prompt[:30] + "..."}

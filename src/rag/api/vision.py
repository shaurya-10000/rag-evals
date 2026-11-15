import logging

from google import genai
from google.genai import types

from rag.config.settings import settings

logger = logging.getLogger("rag.api.vision")

VISION_TIMEOUT_MS = 15000
VISION_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
VISION_PROMPT = "Describe this image in extreme detail. Output only the description."


class VisionError(RuntimeError):
    """Raised when every vision model fails to describe an image."""


def _mime_type(filename: str) -> str:
    if filename.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    return f"image/{filename.rsplit('.', 1)[-1]}"


def describe_image(filename: str, contents: bytes) -> str:
    """Turn an image into searchable text, trying each model in the fallback chain."""
    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=VISION_TIMEOUT_MS),
    )
    mime_type = _mime_type(filename)
    for model in VISION_MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=types.Content(
                    parts=[
                        types.Part.from_bytes(data=contents, mime_type=mime_type),
                        types.Part.from_text(text=VISION_PROMPT),
                    ]
                ),
            )
        except Exception as e:
            logger.warning("vision model %s failed: %s", model, e)
            continue
        if response.text:
            return f"Image Description ({filename}):\n{response.text}"
    raise VisionError("All vision models failed.")

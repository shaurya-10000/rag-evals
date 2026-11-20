"""Rate-limit keys: one bucket per signed-in user, otherwise one per client address.

Requests reach this API from the Next.js server, so the connecting address is the web
host's, not the visitor's. The web app forwards the visitor's address in X-Client-IP, and
it is believed only when the request also carries the shared API key, so nobody calling the
API directly can pick their own bucket.
"""

import secrets

from fastapi import Request
from slowapi.util import get_remote_address

from rag.config.settings import settings

CLIENT_IP_HEADER = "x-client-ip"
MAX_FORWARDED_CHARS = 64


def _from_web_app(request: Request) -> bool:
    supplied = request.headers.get("x-api-key", "")
    return bool(supplied) and secrets.compare_digest(
        supplied.encode(), settings.RAG_API_KEY.encode()
    )


def rate_limit_key(request: Request) -> str:
    # get_current_user stores the id before the limiter runs, so signed-in routes use it.
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    if _from_web_app(request):
        forwarded = request.headers.get(CLIENT_IP_HEADER, "").strip()
        if forwarded:
            return f"ip:{forwarded[:MAX_FORWARDED_CHARS]}"
    return f"ip:{get_remote_address(request)}"

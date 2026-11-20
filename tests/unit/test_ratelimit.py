from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from rag.api.ratelimit import rate_limit_key
from rag.config.settings import settings


def _request(headers: dict[str, str] | None = None, user_id: str | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": ("10.0.0.1", 1234),
        "state": {},
    }
    request = Request(scope)
    if user_id:
        request.state.user_id = user_id
    return request


def test_signed_in_users_get_their_own_key() -> None:
    assert rate_limit_key(_request(user_id="alice")) == "user:alice"
    assert rate_limit_key(_request(user_id="alice")) != rate_limit_key(_request(user_id="bob"))


def test_web_app_can_forward_the_visitor_address() -> None:
    headers = {"x-api-key": settings.RAG_API_KEY, "x-client-ip": "203.0.113.9"}
    assert rate_limit_key(_request(headers)) == "ip:203.0.113.9"


def test_forwarded_address_is_ignored_without_the_api_key() -> None:
    assert rate_limit_key(_request({"x-client-ip": "203.0.113.9"})) == "ip:10.0.0.1"
    wrong = {"x-api-key": "not-the-key", "x-client-ip": "203.0.113.9"}
    assert rate_limit_key(_request(wrong)) == "ip:10.0.0.1"


def _limited_app() -> FastAPI:
    limiter = Limiter(key_func=rate_limit_key)
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    def sign_in(request: Request) -> None:
        request.state.user_id = request.headers.get("x-test-user")

    @app.get("/ask")
    @limiter.limit("2/minute")
    def ask(request: Request, _: None = Depends(sign_in)) -> dict[str, bool]:  # noqa: B008
        return {"ok": True}

    return app


def test_each_user_has_their_own_budget() -> None:
    client = TestClient(_limited_app())
    alice = {"x-test-user": "alice"}
    assert [client.get("/ask", headers=alice).status_code for _ in range(3)] == [200, 200, 429]
    assert client.get("/ask", headers={"x-test-user": "bob"}).status_code == 200

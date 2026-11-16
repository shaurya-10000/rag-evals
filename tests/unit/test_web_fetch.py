import socket

import httpx
import pytest

from rag.ingest import web
from rag.ingest.extractors import ExtractionError

PUBLIC_IP = "93.184.216.34"

PAGE = b"""<html><head><title>Phase Two</title></head><body>
<nav>Home About Pricing</nav>
<main><h1>Phase Two</h1>
<p>Background jobs keep uploads responsive while documents are indexed in batches.</p>
<p>Progress is stored in Postgres so the page can poll it.</p></main>
<script>var tracking = true;</script></body></html>"""


def _resolve_to(monkeypatch: pytest.MonkeyPatch, address: str) -> None:
    def fake(host: str, port: int, **kwargs: object) -> list[tuple[object, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    monkeypatch.setattr(web.socket, "getaddrinfo", fake)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "not a url",
        "http://",
        "ftp://example.com/file",
        "javascript:alert(1)",
        "https://user:pw@example.com/",
        "http://example.com:8080/",
    ],
)
def test_validate_url_rejects(raw: str) -> None:
    with pytest.raises(ExtractionError):
        web.validate_url(raw)


def test_validate_url_accepts_plain_https() -> None:
    assert web.validate_url("  https://example.com/a?b=1 ") == "https://example.com/a?b=1"


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.5",
        "192.168.1.10",
        "169.254.169.254",
        "::1",
        "::ffff:127.0.0.1",
        "fd00::1",
    ],
)
def test_non_public_addresses_are_blocked(monkeypatch: pytest.MonkeyPatch, address: str) -> None:
    _resolve_to(monkeypatch, address)
    with pytest.raises(ExtractionError, match="not allowed"):
        web.fetch_url("https://example.com/")


def test_literal_private_ip_is_blocked_without_dns() -> None:
    with pytest.raises(ExtractionError, match="not allowed"):
        web.fetch_url("http://127.0.0.1/admin")


def test_fetches_html_and_pins_the_validated_address(monkeypatch: pytest.MonkeyPatch) -> None:
    _resolve_to(monkeypatch, PUBLIC_IP)
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["host"] = request.headers["host"]
        return httpx.Response(
            200, headers={"content-type": "text/html; charset=utf-8"}, content=PAGE
        )

    page = web.fetch_url("https://example.com/post", transport=httpx.MockTransport(handler))

    assert page.title == "Phase Two"
    assert "Background jobs keep uploads responsive" in page.text
    assert "Pricing" not in page.text
    assert "tracking" not in page.text
    assert seen["url"].startswith(f"https://{PUBLIC_IP}/post")
    assert seen["host"] == "example.com"


def test_redirect_to_a_private_address_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    _resolve_to(monkeypatch, PUBLIC_IP)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})

    with pytest.raises(ExtractionError, match="not allowed"):
        web.fetch_url("https://example.com/", transport=httpx.MockTransport(handler))


def test_redirect_loops_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    _resolve_to(monkeypatch, PUBLIC_IP)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://example.com/again"})

    with pytest.raises(ExtractionError, match="Too many redirects"):
        web.fetch_url("https://example.com/", transport=httpx.MockTransport(handler))


def test_oversized_pages_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _resolve_to(monkeypatch, PUBLIC_IP)
    headers = {"content-type": "text/html", "content-length": str(web.MAX_UPLOAD_BYTES + 1)}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers=headers, content=b"x")

    with pytest.raises(ExtractionError, match="too large"):
        web.fetch_url("https://example.com/", transport=httpx.MockTransport(handler))


def test_unsupported_content_type_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _resolve_to(monkeypatch, PUBLIC_IP)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=b"\x89PNG")

    with pytest.raises(ExtractionError) as excinfo:
        web.fetch_url("https://example.com/logo.png", transport=httpx.MockTransport(handler))
    assert excinfo.value.status_code == 415


def test_pages_with_almost_no_text_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _resolve_to(monkeypatch, PUBLIC_IP)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"<html><body>Loading...</body></html>",
        )

    with pytest.raises(ExtractionError, match="very little readable text"):
        web.fetch_url("https://example.com/app", transport=httpx.MockTransport(handler))

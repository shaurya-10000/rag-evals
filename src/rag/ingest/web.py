"""Fetch a web page for ingestion, guarded against server-side request forgery (SSRF).

Every hop (including redirects) is validated, the hostname is resolved once and the
connection is pinned to that validated address, so DNS cannot swap in a private IP later.
"""

import ipaddress
import socket
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import SplitResult, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from rag.ingest.extractors import (
    MAX_UPLOAD_BYTES,
    ExtractionError,
    decode_text,
    extract_csv,
    extract_pdf,
    limit_text,
)

MAX_URL_CHARS = 1000  # documents.source_url is 1024 characters
MAX_REDIRECTS = 5
TOTAL_TIMEOUT_SECONDS = 20.0
MIN_PAGE_CHARS = 80
MAX_TITLE_CHARS = 255
ALLOWED_PORTS = (None, 80, 443)
USER_AGENT = "RAGEvalsBot/1.0 (+https://rag-evals.vercel.app)"
ACCEPT = "text/html,application/xhtml+xml,application/pdf,text/plain;q=0.9,*/*;q=0.1"
HTML_TYPES = ("text/html", "application/xhtml+xml")
PLAIN_TYPES = ("text/plain", "text/markdown")
NOISE_TAGS = [
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "iframe",
    "form",
    "nav",
    "footer",
    "aside",
    "button",
]


@dataclass(frozen=True)
class FetchedPage:
    title: str | None
    text: str


def validate_url(raw: str) -> str:
    """Cheap syntax check, safe to run in the request. Returns the cleaned URL."""
    url = raw.strip()
    if not url or len(url) > MAX_URL_CHARS:
        raise ExtractionError("Enter a valid web address.")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise ExtractionError("Enter a valid web address.") from None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ExtractionError("Only http and https web addresses are supported.")
    if parts.username or parts.password:
        raise ExtractionError("Addresses with embedded credentials are not allowed.")
    if port not in ALLOWED_PORTS:
        raise ExtractionError("Only standard web ports (80 and 443) are allowed.")
    return url


def _address_of(info: Any) -> str:
    return str(info[4][0]).split("%")[0]


def _public_addresses(host: str, port: int) -> list[str]:
    """Resolve `host` and return its addresses, refusing anything that is not public."""
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except (socket.gaierror, UnicodeError):
            raise ExtractionError("Could not find that website.") from None
        found = list(dict.fromkeys(_address_of(info) for info in infos))
    else:
        found = [str(literal)]
    if not found:
        raise ExtractionError("Could not find that website.")

    for address in found:
        ip = ipaddress.ip_address(address)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        if not ip.is_global:
            raise ExtractionError("That address is not allowed.")
    return found


def _ascii_host(host: str) -> str:
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        raise ExtractionError("Enter a valid web address.") from None


def _pin(parts: SplitResult, address: str) -> str:
    host = f"[{address}]" if ":" in address else address
    query = f"?{parts.query}" if parts.query else ""
    return f"{parts.scheme}://{host}{parts.path or '/'}{query}"


def _read_limited(response: httpx.Response) -> bytes:
    too_large = ExtractionError("That page is too large (max 10 MB).", status_code=413)
    declared = response.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES:
        raise too_large
    body = bytearray()
    for chunk in response.iter_bytes():
        body.extend(chunk)
        if len(body) > MAX_UPLOAD_BYTES:
            raise too_large
    return bytes(body)


def _get(url: str, transport: httpx.BaseTransport | None) -> tuple[str, bytes]:
    """Return (content type, body), following redirects by hand so each hop is re-checked."""
    deadline = time.monotonic() + TOTAL_TIMEOUT_SECONDS
    current = url
    timeout = httpx.Timeout(10.0, connect=5.0)
    with httpx.Client(
        transport=transport, timeout=timeout, follow_redirects=False, trust_env=False
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            if time.monotonic() > deadline:
                raise ExtractionError("The page took too long to respond.", status_code=504)
            current = validate_url(current)
            parts = urlsplit(current)
            host = _ascii_host(parts.hostname or "")
            port = parts.port or (443 if parts.scheme == "https" else 80)
            address = _public_addresses(host, port)[0]

            headers = {"Host": host, "User-Agent": USER_AGENT, "Accept": ACCEPT}
            extensions = {"sni_hostname": host} if parts.scheme == "https" else {}
            try:
                with client.stream(
                    "GET", _pin(parts, address), headers=headers, extensions=extensions
                ) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise ExtractionError("The site sent an invalid redirect.")
                        current = urljoin(current, location)
                        continue
                    if response.status_code >= 400:
                        raise ExtractionError(
                            f"The site returned an error (HTTP {response.status_code}).",
                            status_code=502,
                        )
                    content_type = response.headers.get("content-type", "")
                    return content_type.split(";")[0].strip().lower(), _read_limited(response)
            except httpx.TimeoutException:
                raise ExtractionError(
                    "The page took too long to respond.", status_code=504
                ) from None
            except httpx.HTTPError:
                raise ExtractionError("Could not reach that website.", status_code=502) from None
    raise ExtractionError("Too many redirects.")


def _page_title(soup: Any) -> str | None:
    meta = soup.find("meta", attrs={"property": "og:title"})
    candidates = [meta.get("content") if meta else None]
    if soup.title is not None:
        candidates.append(soup.title.string)
    for candidate in candidates:
        cleaned = " ".join(str(candidate or "").split())[:MAX_TITLE_CHARS]
        if cleaned:
            return cleaned
    return None


def html_to_text(body: bytes) -> tuple[str | None, str]:
    soup: Any = BeautifulSoup(body, "html.parser")
    title = _page_title(soup)
    for tag in soup(NOISE_TAGS):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    lines = (" ".join(line.split()) for line in root.get_text("\n").splitlines())
    return title, "\n".join(line for line in lines if line)


def _html_page(body: bytes) -> FetchedPage:
    title, text = html_to_text(body)
    if len(text) < MIN_PAGE_CHARS:
        raise ExtractionError(
            "This page has very little readable text. It may need JavaScript or a login."
        )
    return FetchedPage(title=title, text=limit_text(text))


def fetch_url(url: str, transport: httpx.BaseTransport | None = None) -> FetchedPage:
    content_type, body = _get(url, transport)
    if content_type in HTML_TYPES or content_type == "":
        return _html_page(body)
    if content_type == "application/pdf":
        return FetchedPage(title=None, text=extract_pdf(body))
    if content_type in PLAIN_TYPES:
        return FetchedPage(title=None, text=limit_text(decode_text(body)))
    if content_type == "text/csv":
        return FetchedPage(title=None, text=extract_csv(body))
    raise ExtractionError(
        f"Unsupported content type ({content_type}). Use a web page, PDF or text file.",
        status_code=415,
    )

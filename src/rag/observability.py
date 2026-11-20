"""Request ids, structured (JSON) logs and per-request timing.

Every request gets an id (taken from a valid X-Request-ID header, else generated). It is put
on each log line, returned in the response header and logged once more with the status and
total duration when the response, including a streamed one, has finished.
"""

import contextvars
import json
import logging
import os
import re
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from rag.config.settings import settings

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

logger = logging.getLogger("rag.request")
QUIET_PATHS = {"/health"}


def get_request_id() -> str:
    return _request_id.get()


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", _request_id.get()),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s [%(levelname)s] %(name)s [%(request_id)s]: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            line += " " + " ".join(f"{k}={v}" for k, v in fields.items())
        return line


def configure_logging() -> None:
    default = "json" if settings.is_production else "text"
    use_json = os.getenv("LOG_FORMAT", default).lower() == "json"
    handler = logging.StreamHandler()
    handler.addFilter(_RequestIdFilter())
    handler.setFormatter(JsonFormatter() if use_json else TextFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    # RequestContextMiddleware logs every request, so uvicorn's access log would duplicate it.
    logging.getLogger("uvicorn.access").disabled = True


class RequestContextMiddleware:
    """Pure ASGI middleware: unlike BaseHTTPMiddleware it does not interfere with streaming."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(REQUEST_ID_HEADER, "")
        request_id = incoming if _VALID_ID.match(incoming) else new_request_id()
        token = _request_id.set(request_id)
        started = time.perf_counter()
        status = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            path = scope.get("path", "")
            if path not in QUIET_PATHS:
                logger.info(
                    "request",
                    extra={
                        "fields": {
                            "method": scope.get("method"),
                            "path": path,
                            "status": status,
                            "duration_ms": round((time.perf_counter() - started) * 1000),
                        }
                    },
                )
            _request_id.reset(token)

import time
import uuid
from contextvars import ContextVar

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from structlog.contextvars import bind_contextvars, clear_contextvars

_request_id_var: ContextVar[str] = ContextVar("request_id", default="not_provided")


def get_request_id() -> str:
    return _request_id_var.get()


class LoggingMiddleware:
    """Pure-ASGI logging middleware.

    Uses raw ASGI instead of starlette.middleware.base.BaseHTTPMiddleware because
    the latter wraps the downstream app in a child anyio task whose contextvar
    inheritance is unreliable — log records from inside the endpoint (LiteLLM,
    services, etc.) would miss the request_id bound here. Raw ASGI runs the
    downstream app in the same task scope as the binding, so merge_contextvars
    picks up request_id everywhere.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _extract_request_id(scope)
        _request_id_var.set(request_id)
        bind_contextvars(request_id=request_id)

        logger = structlog.get_logger().bind(
            method=scope["method"],
            path=scope["path"],
            client_ip=scope["client"][0] if scope.get("client") else None,
        )
        logger.info("request_started")
        start_time = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.exception("request_failed", duration_ms=round(duration_ms, 2), error=str(e))
            raise
        else:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "request_completed",
                status_code=status_code,
                duration_ms=round(duration_ms, 2),
            )
        finally:
            clear_contextvars()


def _extract_request_id(scope: Scope) -> str:
    headers: list[tuple[bytes, bytes]] = scope.get("headers", [])
    for name, value in headers:
        if name == b"x-request-id":
            return value.decode()
    return str(uuid.uuid4())

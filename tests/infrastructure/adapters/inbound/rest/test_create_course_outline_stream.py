from collections.abc import AsyncGenerator
from types import SimpleNamespace

from fastapi.testclient import TestClient

from coursesmith.app import app
from coursesmith.infrastructure.adapters.inbound.rest.create_course_outline_adapter import (
    get_service,
)


async def _fake_create_stream(topic: str) -> AsyncGenerator[str, None]:
    """Yield two pre-canned tokens. Mirrors the shape of the real stream."""
    _ = topic
    yield "Hello"
    yield " world"


def test_post_courses_stream_emits_sse_tokens_and_done():
    fake = SimpleNamespace(create_stream=_fake_create_stream)
    app.dependency_overrides[get_service] = lambda: fake
    try:
        with TestClient(app) as client:
            resp = client.post("/courses/stream", json={"topic": "AI engineering"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = resp.text
        # Each yielded token becomes a JSON-encoded `data:` line on a `token` event.
        assert "event: token" in body
        assert 'data: "Hello"' in body
        assert 'data: " world"' in body
        # The terminator uses raw_data, so the [DONE] payload is unquoted.
        assert "event: done" in body
        assert "data: [DONE]" in body
        # Order: tokens precede the terminator.
        assert body.index('data: "Hello"') < body.index("data: [DONE]")
        assert body.index('data: " world"') < body.index("data: [DONE]")
    finally:
        app.dependency_overrides.clear()

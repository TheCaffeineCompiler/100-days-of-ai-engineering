"""Day 10 capstone integration test.

Exercises the full POST /courses path — routing, request parsing,
FastAPI dependency resolution, the use-case service, the file-backed
prompt loader, and JSON validation — with the LLM stubbed at the
LlmPort boundary. Asserts the endpoint's response validates against
CourseOutline.
"""

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient

from coursesmith import RESOURCES_DIR
from coursesmith.app import app
from coursesmith.composition import get_service
from coursesmith.infrastructure.shared.adapters.outbound.prompts_adapter import PromptsAdapter
from coursesmith.settings import settings
from coursesmith.use_cases.create_course_outline.course_outline_service import CourseOutlineService
from coursesmith.use_cases.create_course_outline.models.course_outline import CourseOutline
from coursesmith.use_cases.shared.ports.llm_port import LlmPort

_CANNED_OUTLINE = CourseOutline(
    title="Two-day intro to git",
    day_items=[],
)


class _StubLlmPort(LlmPort):
    """Returns a ModelResponse-shaped object whose JSON content parses as a CourseOutline."""

    async def complete(
        self,
        messages: list[dict[str, str]],  # noqa: ARG002
        response_format: type,  # noqa: ARG002
        tools: list[dict[str, Any]] | None = None,  # noqa: ARG002
    ) -> Any:
        message = SimpleNamespace(
            content=_CANNED_OUTLINE.model_dump_json(),
            tool_calls=None,
        )
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])

    async def stream(  # pragma: no cover
        self,
        messages: list[dict[str, str]],  # noqa: ARG002
    ) -> AsyncIterator[Any]:
        if False:
            yield


def _build_service_with_stub_llm() -> CourseOutlineService:
    return CourseOutlineService(
        llm_port=_StubLlmPort(),
        prompts_port=PromptsAdapter(base_path=RESOURCES_DIR),
        prompt_version=settings.course_outline_prompt_version,
    )


def test_post_courses_returns_validated_course_outline():
    """End-to-end: real route + service + prompt loader + stub LLM → response parses as CourseOutline."""
    app.dependency_overrides[get_service] = _build_service_with_stub_llm
    try:
        with TestClient(app) as client:
            resp = client.post("/courses", json={"topic": "Two-day intro to git"})
        assert resp.status_code == 200
        validated = CourseOutline.model_validate(resp.json())
        assert validated == _CANNED_OUTLINE
    finally:
        app.dependency_overrides.clear()

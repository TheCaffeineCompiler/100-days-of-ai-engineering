"""Tests for `ReviewCourseTool` — schema shape and execute → LLM plumbing.

This is the only tool wired with a `response_type`, since its output is
the final `CourseOutline` shape the service validates.
"""

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

from coursesmith.use_cases.create_course_outline.models.course_outline import CourseOutline
from coursesmith.use_cases.create_course_outline.tools.review_course_tool import (
    ReviewCourseParams,
    ReviewCourseTool,
)
from coursesmith.use_cases.shared.ports.llm_port import LlmPort
from coursesmith.use_cases.shared.ports.prompts_port import PromptsPort


class _StubPromptsPort(PromptsPort):
    def __init__(self, template: str) -> None:
        self._template = template
        self.calls: list[tuple[str, int]] = []

    def get_prompt(self, name: str, version: int) -> str:
        self.calls.append((name, version))
        return self._template


class _RecordingLlmPort(LlmPort):
    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        messages: list[dict[str, str]],
        response_format: type | None,
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        self.calls.append(
            {"messages": messages, "response_format": response_format, "tools": tools}
        )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._content))]
        )

    async def stream(  # pragma: no cover
        self,
        messages: list[dict[str, str]],  # noqa: ARG002
    ) -> AsyncIterator[Any]:
        if False:
            yield


def _make_tool() -> tuple[ReviewCourseTool, _StubPromptsPort, _RecordingLlmPort]:
    llm = _RecordingLlmPort(content='{"title": "x", "day_items": []}')
    prompts = _StubPromptsPort(template="Title: {title}\nContent: {content}")
    tool = ReviewCourseTool(
        llm_port=llm,
        prompts_port=prompts,
        prompts_name="review_course",
        prompts_version=1,
        response_type=CourseOutline,
    )
    return tool, prompts, llm


def test_get_name():
    tool, _, _ = _make_tool()
    assert tool.get_name() == "review_course"


def test_get_schema_shape():
    tool, _, _ = _make_tool()
    schema = tool.get_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "review_course"
    assert "improve" in schema["function"]["description"].lower()
    assert schema["function"]["parameters"] == ReviewCourseParams.model_json_schema()


def test_content_field_has_no_default_and_carries_a_description():
    """Regression: an earlier version had `content: str = "joined list of day items"`,
    which leaked a placeholder string as the default value. The fix moved that text
    into a Field description; content must remain required."""
    schema = ReviewCourseParams.model_json_schema()
    content_schema = schema["properties"]["content"]
    assert "default" not in content_schema
    assert "description" in content_schema
    assert "content" in schema["required"]


def test_execute_renders_prompt_and_returns_llm_content():
    tool, prompts, llm = _make_tool()
    result = asyncio.run(
        tool.execute({"title": "Intro to git", "content": "Day 1: ...; Day 2: ..."})
    )

    assert result == '{"title": "x", "day_items": []}'
    assert prompts.calls == [("review_course", 1)]
    assert llm.calls[0]["messages"] == [
        {"role": "user", "content": "Title: Intro to git\nContent: Day 1: ...; Day 2: ..."}
    ]
    # Final stage: response_format MUST be the CourseOutline model so the inner
    # LLM call returns a JSON object the service can validate.
    assert llm.calls[0]["response_format"] is CourseOutline

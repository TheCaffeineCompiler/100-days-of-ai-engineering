"""Tests for `CreateScheduleTool` — schema shape and execute → LLM plumbing."""

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

from coursesmith.use_cases.create_course_outline.tools.create_schedule_tool import (
    CreateScheduleParams,
    CreateScheduleTool,
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


def _make_tool() -> tuple[CreateScheduleTool, _StubPromptsPort, _RecordingLlmPort]:
    llm = _RecordingLlmPort(content="Day 1: ...\nDay 2: ...")
    prompts = _StubPromptsPort(template="Title: {title}")
    tool = CreateScheduleTool(
        llm_port=llm,
        prompts_port=prompts,
        prompts_name="course_schedule",
        prompts_version=1,
    )
    return tool, prompts, llm


def test_get_name():
    tool, _, _ = _make_tool()
    assert tool.get_name() == "create_schedule"


def test_get_schema_shape():
    tool, _, _ = _make_tool()
    schema = tool.get_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "create_schedule"
    assert "schedule" in schema["function"]["description"].lower()
    assert schema["function"]["parameters"] == CreateScheduleParams.model_json_schema()


def test_execute_renders_prompt_and_returns_llm_content():
    tool, prompts, llm = _make_tool()
    result = asyncio.run(tool.execute({"title": "Intro to git"}))

    assert result == "Day 1: ...\nDay 2: ..."
    assert prompts.calls == [("course_schedule", 1)]
    assert llm.calls[0]["messages"] == [{"role": "user", "content": "Title: Intro to git"}]
    # Schedule output is free text — `response_format` must be None, otherwise the
    # schedule sub-LLM would be coerced into producing the final CourseOutline shape.
    assert llm.calls[0]["response_format"] is None

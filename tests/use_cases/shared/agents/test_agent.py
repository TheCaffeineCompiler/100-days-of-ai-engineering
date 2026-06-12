"""Tests for the Agent loop.

Covers `run` (text-only path, tool round-trip, max_steps exhaustion) and
`stream` (final-answer streaming after zero or more tool rounds). The
LlmPort and PromptsPort are stubbed; tools are fake `AgentTool`
subclasses that record their inputs.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from coursesmith.use_cases.shared.agents.agent import Agent, AgentLoopExhaustedError
from coursesmith.use_cases.shared.agents.agent_tool import AgentTool
from coursesmith.use_cases.shared.ports.llm_port import LlmPort
from coursesmith.use_cases.shared.ports.prompts_port import PromptsPort


# --- Stubs ---------------------------------------------------------------


class _StubPromptsPort(PromptsPort):
    def __init__(self, template: str = "topic={topic}") -> None:
        self._template = template

    def get_prompt(self, name: str, version: int) -> str:  # noqa: ARG002
        return self._template


def _text_response(content: str) -> Any:
    """Shape a ModelResponse whose assistant message returns text (no tool calls)."""
    message = SimpleNamespace(content=content, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _tool_call_response(tool_name: str, arguments: dict[str, Any], call_id: str = "c1") -> Any:
    """Shape a ModelResponse whose assistant message requests one tool call."""
    tc = SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=tool_name, arguments=json.dumps(arguments)),
    )
    message = SimpleNamespace(content=None, tool_calls=[tc])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _stream_chunk(content: str | None) -> Any:
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=content))])


class _CountingLlmPort(LlmPort):
    """Yields canned `complete` results in order and records every call."""

    def __init__(self, complete_responses: list[Any], stream_tokens: list[str | None] | None = None):
        self._complete_responses = list(complete_responses)
        self._stream_tokens = list(stream_tokens or [])
        self.complete_calls: list[dict[str, Any]] = []
        self.stream_calls: list[list[dict[str, Any]]] = []

    async def complete(
        self,
        messages: list[dict[str, str]],
        response_format: type | None,
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        self.complete_calls.append(
            {"messages": list(messages), "response_format": response_format, "tools": tools}
        )
        return self._complete_responses.pop(0)

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[Any]:
        self.stream_calls.append(list(messages))
        for token in self._stream_tokens:
            yield _stream_chunk(token)


class _StubParams(BaseModel):
    title: str


class _RecordingTool(AgentTool[_StubParams]):
    """Tool whose `_execute` returns a canned string and records the params."""

    def __init__(self, tool_name: str = "create_title", result: str = "Some Title") -> None:
        self._name = tool_name
        self._result = result
        self.calls: list[_StubParams] = []

    def name(self) -> str:
        return self._name

    def description(self) -> str:
        return f"recorded tool {self._name}"

    def params_cls(self) -> type[_StubParams]:
        return _StubParams

    async def _execute(self, params: _StubParams) -> Any:
        self.calls.append(params)
        return self._result


# --- run() ---------------------------------------------------------------


def test_run_returns_content_directly_on_no_tool_call():
    llm = _CountingLlmPort([_text_response('{"title": "x", "day_items": []}')])
    agent = Agent(llm_port=llm, prompts_port=_StubPromptsPort())

    result = asyncio.run(
        agent.run(
            prompt_name="course_outline",
            prompt_version=1,
            tools=[],
            prompt_params={"topic": "git"},
        )
    )

    assert result == '{"title": "x", "day_items": []}'
    assert len(llm.complete_calls) == 1
    # The prompt template was rendered and placed as the user message.
    assert llm.complete_calls[0]["messages"] == [{"role": "user", "content": "topic=git"}]


def test_run_executes_tool_then_returns_final_answer():
    """One tool round-trip: model requests a tool, agent executes it, model returns text."""
    tool = _RecordingTool(tool_name="create_title", result="A Great Title")
    llm = _CountingLlmPort(
        [
            _tool_call_response("create_title", {"title": "git"}),
            _text_response("Final outline content."),
        ]
    )
    agent = Agent(llm_port=llm, prompts_port=_StubPromptsPort())

    result = asyncio.run(
        agent.run(
            prompt_name="course_outline",
            prompt_version=1,
            tools=[tool],
            prompt_params={"topic": "git"},
        )
    )

    assert result == "Final outline content."
    # Tool received validated params.
    assert tool.calls == [_StubParams(title="git")]
    # Two outer LLM calls: discovery + final.
    assert len(llm.complete_calls) == 2
    # Second call's messages carry the assistant tool_call message AND the tool reply.
    second_messages = llm.complete_calls[1]["messages"]
    tool_replies = [m for m in second_messages if isinstance(m, dict) and m.get("role") == "tool"]
    assert len(tool_replies) == 1
    assert tool_replies[0]["tool_call_id"] == "c1"
    assert tool_replies[0]["name"] == "create_title"
    assert tool_replies[0]["content"] == "A Great Title"


def test_run_raises_agent_loop_exhausted_with_original_budget_in_message():
    """If the model keeps requesting tools past max_steps, surface a typed error and
    cite the *original* budget (not the post-decrement zero)."""
    tool = _RecordingTool()
    # Every iteration requests another tool call → loop never returns text.
    looping = [_tool_call_response("create_title", {"title": f"t{i}"}) for i in range(10)]
    llm = _CountingLlmPort(looping)
    agent = Agent(llm_port=llm, prompts_port=_StubPromptsPort())

    with pytest.raises(AgentLoopExhaustedError) as exc_info:
        asyncio.run(
            agent.run(
                prompt_name="course_outline",
                prompt_version=1,
                tools=[tool],
                prompt_params={"topic": "git"},
                max_steps=3,
            )
        )

    assert "3" in str(exc_info.value)
    assert len(llm.complete_calls) == 3


def test_run_dispatches_to_the_tool_whose_name_matches():
    """Two tools registered; the model picks the second one — only that one runs."""
    title_tool = _RecordingTool(tool_name="create_title", result="title-result")
    schedule_tool = _RecordingTool(tool_name="create_schedule", result="schedule-result")
    llm = _CountingLlmPort(
        [
            _tool_call_response("create_schedule", {"title": "git"}),
            _text_response("done"),
        ]
    )
    agent = Agent(llm_port=llm, prompts_port=_StubPromptsPort())

    asyncio.run(
        agent.run(
            prompt_name="course_outline",
            prompt_version=1,
            tools=[title_tool, schedule_tool],
            prompt_params={"topic": "git"},
        )
    )

    assert title_tool.calls == []
    assert schedule_tool.calls == [_StubParams(title="git")]


# --- stream() ------------------------------------------------------------


def test_stream_yields_tokens_after_no_tool_call_round():
    """Discovery call returns no tools → re-issue as stream → yield each chunk's content."""
    llm = _CountingLlmPort(
        complete_responses=[_text_response("(unused — we switch to streaming)")],
        stream_tokens=["Hello", " ", "world"],
    )
    agent = Agent(llm_port=llm, prompts_port=_StubPromptsPort())

    async def _collect() -> list[str]:
        return [t async for t in agent.stream(
            prompt_name="course_outline",
            prompt_version=1,
            tools=[],
            prompt_params={"topic": "git"},
        )]

    tokens = asyncio.run(_collect())
    assert tokens == ["Hello", " ", "world"]
    assert len(llm.complete_calls) == 1
    assert len(llm.stream_calls) == 1


def test_stream_skips_empty_delta_content():
    """LiteLLM emits chunks with `content=None` (e.g. role-only first chunk); the
    agent must not yield those."""
    llm = _CountingLlmPort(
        complete_responses=[_text_response("(unused)")],
        stream_tokens=[None, "tok1", None, "tok2", None],
    )
    agent = Agent(llm_port=llm, prompts_port=_StubPromptsPort())

    async def _collect() -> list[str]:
        return [t async for t in agent.stream(
            prompt_name="course_outline",
            prompt_version=1,
            tools=[],
            prompt_params={"topic": "git"},
        )]

    assert asyncio.run(_collect()) == ["tok1", "tok2"]


def test_stream_runs_tool_round_before_streaming_final_answer():
    """Tool round happens via `complete`; only the final answer is streamed."""
    tool = _RecordingTool(tool_name="create_title", result="My Title")
    llm = _CountingLlmPort(
        complete_responses=[
            _tool_call_response("create_title", {"title": "git"}),
            _text_response("(unused — switching to stream)"),
        ],
        stream_tokens=["The", " ", "Answer"],
    )
    agent = Agent(llm_port=llm, prompts_port=_StubPromptsPort())

    async def _collect() -> list[str]:
        return [t async for t in agent.stream(
            prompt_name="course_outline",
            prompt_version=1,
            tools=[tool],
            prompt_params={"topic": "git"},
        )]

    tokens = asyncio.run(_collect())
    assert tokens == ["The", " ", "Answer"]
    assert tool.calls == [_StubParams(title="git")]
    # Two `complete` calls (discovery + post-tool), one `stream` call (final answer).
    assert len(llm.complete_calls) == 2
    assert len(llm.stream_calls) == 1


def test_stream_raises_agent_loop_exhausted_with_original_budget():
    looping = [_tool_call_response("create_title", {"title": f"t{i}"}) for i in range(10)]
    llm = _CountingLlmPort(complete_responses=looping)
    tool = _RecordingTool()
    agent = Agent(llm_port=llm, prompts_port=_StubPromptsPort())

    async def _drain() -> None:
        async for _ in agent.stream(
            prompt_name="course_outline",
            prompt_version=1,
            tools=[tool],
            prompt_params={"topic": "git"},
            max_steps=2,
        ):
            pass

    with pytest.raises(AgentLoopExhaustedError) as exc_info:
        asyncio.run(_drain())

    assert "2" in str(exc_info.value)

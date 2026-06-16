"""Tests for the Agent loop.

Covers `run` (text-only path, tool round-trip, max_steps / cost / time
exhaustion) and `stream` (final-answer streaming after zero or more
tool rounds). The LlmPort, PromptsPort and UsageTracker are stubbed;
tools are fake `AgentTool` subclasses that record their inputs.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from coursesmith.infrastructure.shared.observability.usage_tracker import (
    UsageModel,
    UsageTracker,
)
from coursesmith.use_cases.shared.agents.agent import (
    Agent,
    AgentLoopExhaustedError,
    AgentResult,
)
from coursesmith.use_cases.shared.agents.agent_tool import AgentTool
from coursesmith.use_cases.shared.ports.llm_port import LlmPort
from coursesmith.use_cases.shared.ports.prompts_port import PromptsPort

# --- Stubs ---------------------------------------------------------------


class _StubPromptsPort(PromptsPort):
    def __init__(self, template: str = "topic={topic}") -> None:
        self._template = template

    def get_prompt(self, name: str, version: int) -> str:  # noqa: ARG002
        return self._template


class _FixedCostUsageTracker(UsageTracker):
    """UsageTracker whose `snapshot` returns a fixed cost regardless of request_id.
    Lets tests rig the cost budget without binding a contextvar."""

    def __init__(self, cost_in_dollars: float = 0.0) -> None:
        super().__init__()
        self._cost = cost_in_dollars

    def snapshot(self, request_id: str) -> UsageModel | None:  # noqa: ARG002
        return UsageModel(prompt=0, completion=0, cost=self._cost)


def _text_response(content: str) -> Any:
    """Shape a ModelResponse whose assistant message returns text (no tool calls)."""
    message = SimpleNamespace(content=content, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _tool_call_response(tool_name: str, arguments: dict[str, Any], call_id: str = "c1") -> Any:
    """Shape a ModelResponse whose assistant message requests one tool call."""
    return _tool_calls_response([(tool_name, arguments, call_id)])


def _tool_calls_response(calls: list[tuple[str, dict[str, Any], str]]) -> Any:
    """Shape a ModelResponse whose assistant message requests several tool calls in one turn."""
    tcs = [
        SimpleNamespace(
            id=call_id,
            function=SimpleNamespace(name=name, arguments=json.dumps(args)),
        )
        for name, args, call_id in calls
    ]
    message = SimpleNamespace(content=None, tool_calls=tcs)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _stream_chunk(content: str | None) -> Any:
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=content))])


class _CountingLlmPort(LlmPort):
    """Yields canned `complete` results in order and records every call."""

    def __init__(
        self, complete_responses: list[Any], stream_tokens: list[str | None] | None = None
    ):
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


class _SlowTool(AgentTool[_StubParams]):
    """Tool whose `_execute` sleeps `delay` seconds before returning a canned string."""

    def __init__(self, tool_name: str, delay: float, result: str = "ok") -> None:
        self._name = tool_name
        self._delay = delay
        self._result = result

    def name(self) -> str:
        return self._name

    def description(self) -> str:
        return f"slow tool {self._name}"

    def params_cls(self) -> type[_StubParams]:
        return _StubParams

    async def _execute(self, params: _StubParams) -> Any:  # noqa: ARG002
        await asyncio.sleep(self._delay)
        return self._result


class _FailingTool(AgentTool[_StubParams]):
    """Tool whose `_execute` always raises — used to verify failure isolation."""

    def __init__(self, tool_name: str, error_message: str = "boom") -> None:
        self._name = tool_name
        self._error_message = error_message

    def name(self) -> str:
        return self._name

    def description(self) -> str:
        return f"failing tool {self._name}"

    def params_cls(self) -> type[_StubParams]:
        return _StubParams

    async def _execute(self, params: _StubParams) -> Any:  # noqa: ARG002
        raise RuntimeError(self._error_message)


def _make_agent(llm: LlmPort, *, cost_in_dollars: float = 0.0) -> Agent:
    return Agent(
        llm_port=llm,
        prompts_port=_StubPromptsPort(),
        usage_tracker=_FixedCostUsageTracker(cost_in_dollars=cost_in_dollars),
    )


# --- run() ---------------------------------------------------------------


def test_run_returns_agent_result_with_finished_stop_reason_and_content():
    llm = _CountingLlmPort([_text_response('{"title": "x", "day_items": []}')])
    agent = _make_agent(llm)

    result = asyncio.run(
        agent.run(
            prompt_name="course_outline",
            prompt_version=1,
            tools=[],
            prompt_params={"topic": "git"},
        )
    )

    assert isinstance(result, AgentResult)
    assert result.stop_reason == "finished"
    assert result.result == '{"title": "x", "day_items": []}'
    assert len(llm.complete_calls) == 1
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
    agent = _make_agent(llm)

    result = asyncio.run(
        agent.run(
            prompt_name="course_outline",
            prompt_version=1,
            tools=[tool],
            prompt_params={"topic": "git"},
        )
    )

    assert result.stop_reason == "finished"
    assert result.result == "Final outline content."
    assert tool.calls == [_StubParams(title="git")]
    assert len(llm.complete_calls) == 2
    second_messages = llm.complete_calls[1]["messages"]
    tool_replies = [m for m in second_messages if isinstance(m, dict) and m.get("role") == "tool"]
    assert len(tool_replies) == 1
    assert tool_replies[0]["tool_call_id"] == "c1"
    assert tool_replies[0]["name"] == "create_title"
    assert tool_replies[0]["content"] == "A Great Title"


def test_run_dispatches_to_the_tool_whose_name_matches():
    title_tool = _RecordingTool(tool_name="create_title", result="title-result")
    schedule_tool = _RecordingTool(tool_name="create_schedule", result="schedule-result")
    llm = _CountingLlmPort(
        [
            _tool_call_response("create_schedule", {"title": "git"}),
            _text_response("done"),
        ]
    )
    agent = _make_agent(llm)

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


def test_run_raises_with_too_many_steps_when_max_steps_exhausted():
    """If the model keeps requesting tools past max_steps, surface a typed error
    whose payload is an AgentResult with stop_reason='too_many_steps'."""
    tool = _RecordingTool()
    looping = [_tool_call_response("create_title", {"title": f"t{i}"}) for i in range(10)]
    llm = _CountingLlmPort(looping)
    agent = _make_agent(llm)

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

    payload = exc_info.value.args[0]
    assert isinstance(payload, AgentResult)
    assert payload.stop_reason == "too_many_steps"
    assert payload.result is None
    assert len(llm.complete_calls) == 3


def test_run_raises_with_costs_too_high_when_cumulative_cost_exceeds_budget():
    """The usage tracker reports a high cumulative cost on the first check;
    the loop must abort before any LLM call."""
    llm = _CountingLlmPort([_text_response("never reached")])
    # 10 cents already spent; budget is 5 cents → trips on the first check.
    agent = _make_agent(llm, cost_in_dollars=0.10)

    with pytest.raises(AgentLoopExhaustedError) as exc_info:
        asyncio.run(
            agent.run(
                prompt_name="course_outline",
                prompt_version=1,
                tools=[],
                prompt_params={"topic": "git"},
                max_costs_in_cents=5.0,
            )
        )

    payload = exc_info.value.args[0]
    assert payload.stop_reason == "costs_too_high"
    assert payload.result is None
    assert len(llm.complete_calls) == 0


def test_run_raises_with_timeout_exceeded_when_wall_clock_budget_is_zero():
    """A 0-second budget is exceeded as soon as the loop's first check runs."""
    llm = _CountingLlmPort([_text_response("never reached")])
    agent = _make_agent(llm)

    with pytest.raises(AgentLoopExhaustedError) as exc_info:
        asyncio.run(
            agent.run(
                prompt_name="course_outline",
                prompt_version=1,
                tools=[],
                prompt_params={"topic": "git"},
                max_time_in_sec=0.0,
            )
        )

    payload = exc_info.value.args[0]
    assert payload.stop_reason == "timeout_exceeded"
    assert payload.result is None
    assert len(llm.complete_calls) == 0


# --- parallel tool calls -------------------------------------------------


def test_run_executes_parallel_tool_calls_concurrently():
    """Two slow tools requested in one turn should overlap, not serialize."""
    slow_a = _SlowTool(tool_name="slow_a", delay=0.15, result="A")
    slow_b = _SlowTool(tool_name="slow_b", delay=0.15, result="B")
    llm = _CountingLlmPort(
        [
            _tool_calls_response(
                [
                    ("slow_a", {"title": "x"}, "c1"),
                    ("slow_b", {"title": "y"}, "c2"),
                ]
            ),
            _text_response("done"),
        ]
    )
    agent = _make_agent(llm)

    async def _run_and_time() -> float:
        start = asyncio.get_event_loop().time()
        await agent.run(
            prompt_name="course_outline",
            prompt_version=1,
            tools=[slow_a, slow_b],
            prompt_params={"topic": "git"},
        )
        return asyncio.get_event_loop().time() - start

    elapsed = asyncio.run(_run_and_time())
    # Concurrent: ~0.15s. Serial would be ~0.30s. 0.25s gives generous CI headroom.
    assert elapsed < 0.25, f"tools appear to have run serially (elapsed={elapsed:.3f}s)"


def test_run_isolates_failing_tool_call_and_reports_error_to_model():
    """If one of two parallel tool calls raises, the sibling still runs and the
    model gets a `tool` message tied to *both* tool_call_ids."""
    good = _RecordingTool(tool_name="good_tool", result="ok-result")
    bad = _FailingTool(tool_name="bad_tool", error_message="kaboom")
    llm = _CountingLlmPort(
        [
            _tool_calls_response(
                [
                    ("good_tool", {"title": "x"}, "c1"),
                    ("bad_tool", {"title": "y"}, "c2"),
                ]
            ),
            _text_response("final"),
        ]
    )
    agent = _make_agent(llm)

    result = asyncio.run(
        agent.run(
            prompt_name="course_outline",
            prompt_version=1,
            tools=[good, bad],
            prompt_params={"topic": "git"},
        )
    )

    assert result.stop_reason == "finished"
    assert good.calls == [_StubParams(title="x")]
    second_messages = llm.complete_calls[1]["messages"]
    tool_replies = [m for m in second_messages if isinstance(m, dict) and m.get("role") == "tool"]
    by_id = {m["tool_call_id"]: m for m in tool_replies}
    assert set(by_id.keys()) == {"c1", "c2"}
    assert by_id["c1"]["content"] == "ok-result"
    error_payload = json.loads(by_id["c2"]["content"])
    assert "kaboom" in error_payload["error"]


def test_run_reports_unknown_tool_as_error_tied_to_tool_call_id():
    """If the model requests a tool that isn't registered, the agent must still
    answer the tool_call_id with an error envelope — otherwise the next request
    is rejected for missing a tool result."""
    llm = _CountingLlmPort(
        [
            _tool_call_response("does_not_exist", {"title": "x"}, call_id="c1"),
            _text_response("recovered"),
        ]
    )
    agent = _make_agent(llm)

    result = asyncio.run(
        agent.run(
            prompt_name="course_outline",
            prompt_version=1,
            tools=[],
            prompt_params={"topic": "git"},
        )
    )

    assert result.stop_reason == "finished"
    second_messages = llm.complete_calls[1]["messages"]
    tool_replies = [m for m in second_messages if isinstance(m, dict) and m.get("role") == "tool"]
    assert len(tool_replies) == 1
    assert tool_replies[0]["tool_call_id"] == "c1"
    error_payload = json.loads(tool_replies[0]["content"])
    assert "does_not_exist" in error_payload["error"]


# --- stream() ------------------------------------------------------------


def test_stream_yields_tokens_after_no_tool_call_round():
    """Discovery call returns no tools → re-issue as stream → yield each chunk's content."""
    llm = _CountingLlmPort(
        complete_responses=[_text_response("(unused — we switch to streaming)")],
        stream_tokens=["Hello", " ", "world"],
    )
    agent = _make_agent(llm)

    async def _collect() -> list[str]:
        return [
            t
            async for t in agent.stream(
                prompt_name="course_outline",
                prompt_version=1,
                tools=[],
                prompt_params={"topic": "git"},
            )
        ]

    tokens = asyncio.run(_collect())
    assert tokens == ["Hello", " ", "world"]
    assert len(llm.complete_calls) == 1
    assert len(llm.stream_calls) == 1


def test_stream_skips_empty_delta_content():
    llm = _CountingLlmPort(
        complete_responses=[_text_response("(unused)")],
        stream_tokens=[None, "tok1", None, "tok2", None],
    )
    agent = _make_agent(llm)

    async def _collect() -> list[str]:
        return [
            t
            async for t in agent.stream(
                prompt_name="course_outline",
                prompt_version=1,
                tools=[],
                prompt_params={"topic": "git"},
            )
        ]

    assert asyncio.run(_collect()) == ["tok1", "tok2"]


def test_stream_runs_tool_round_before_streaming_final_answer():
    tool = _RecordingTool(tool_name="create_title", result="My Title")
    llm = _CountingLlmPort(
        complete_responses=[
            _tool_call_response("create_title", {"title": "git"}),
            _text_response("(unused — switching to stream)"),
        ],
        stream_tokens=["The", " ", "Answer"],
    )
    agent = _make_agent(llm)

    async def _collect() -> list[str]:
        return [
            t
            async for t in agent.stream(
                prompt_name="course_outline",
                prompt_version=1,
                tools=[tool],
                prompt_params={"topic": "git"},
            )
        ]

    tokens = asyncio.run(_collect())
    assert tokens == ["The", " ", "Answer"]
    assert tool.calls == [_StubParams(title="git")]
    assert len(llm.complete_calls) == 2
    assert len(llm.stream_calls) == 1


def test_stream_raises_with_too_many_steps_when_max_steps_exhausted():
    looping = [_tool_call_response("create_title", {"title": f"t{i}"}) for i in range(10)]
    llm = _CountingLlmPort(complete_responses=looping)
    tool = _RecordingTool()
    agent = _make_agent(llm)

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

    payload = exc_info.value.args[0]
    assert isinstance(payload, AgentResult)
    assert payload.stop_reason == "too_many_steps"

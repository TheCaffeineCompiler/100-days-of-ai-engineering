import json
import time
from collections.abc import AsyncIterator
from typing import Any

import structlog
from pydantic import BaseModel
from structlog.contextvars import get_contextvars

from coursesmith.infrastructure.shared.observability.usage_tracker import UsageTracker
from coursesmith.use_cases.shared.agents.agent_tool import AgentTool
from coursesmith.use_cases.shared.ports.llm_port import LlmPort
from coursesmith.use_cases.shared.ports.prompts_port import PromptsPort


class AgentResult[T: BaseModel](BaseModel):
    stop_reason: str
    result: T | str | None


class AgentLoopExhaustedError(Exception):
    def __init__(self, context: AgentResult[Any]):
        super().__init__(context)


class Agent:
    def __init__(
        self,
        llm_port: LlmPort,
        prompts_port: PromptsPort,
        usage_tracker: UsageTracker,
    ):
        self._llm_port = llm_port
        self._prompts_port = prompts_port
        self._usage_tracker = usage_tracker
        self._logger = structlog.get_logger()

    async def run[T: BaseModel](
        self,
        prompt_name: str,
        prompt_version: int,
        tools: list[AgentTool[Any]],
        prompt_params: dict[str, Any],
        response_format: type[T] | None = None,
        max_steps: int = 5,
        max_costs_in_cents: float = 5.0,
        max_time_in_sec: float = 30.0,
    ) -> AgentResult[T]:
        template = self._prompts_port.get_prompt(name=prompt_name, version=prompt_version)
        prompt = template.format(**prompt_params)
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

        loop_start = time.perf_counter()
        while True:
            max_steps -= 1
            self._check_stop_conditions(
                max_steps=max_steps,
                loop_start=loop_start,
                max_costs_in_cents=max_costs_in_cents,
                max_time_in_sec=max_time_in_sec,
            )

            result = await self._llm_port.complete(
                messages=messages,
                response_format=response_format,
                tools=[t.get_schema() for t in tools],
            )

            tool_calls = result.choices[0].message.tool_calls
            if tool_calls:
                await self._handle_tool_call(messages, result, tool_calls, tools)
            else:
                return AgentResult(stop_reason="finished", result=result.choices[0].message.content)

    async def stream(
        self,
        prompt_name: str,
        prompt_version: int,
        tools: list[AgentTool[Any]],
        prompt_params: dict[str, Any],
        max_steps: int = 5,
        max_costs_in_cents: float = 5.0,
        max_time_in_sec: float = 30.0,
    ) -> AsyncIterator[str]:
        template = self._prompts_port.get_prompt(name=prompt_name, version=prompt_version)
        prompt = template.format(**prompt_params)
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

        loop_start = time.perf_counter()
        while True:
            max_steps -= 1
            self._check_stop_conditions(
                max_steps=max_steps,
                loop_start=loop_start,
                max_costs_in_cents=max_costs_in_cents,
                max_time_in_sec=max_time_in_sec,
            )

            result = await self._llm_port.complete(
                messages=messages,
                response_format=None,
                tools=[t.get_schema() for t in tools],
            )

            tool_calls = result.choices[0].message.tool_calls
            if tool_calls:
                await self._handle_tool_call(messages, result, tool_calls, tools)
            else:
                async for chunk in self._llm_port.stream(messages=messages):
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
                return

    def _check_stop_conditions(
        self,
        max_steps: int,
        loop_start: float,
        max_costs_in_cents: float,
        max_time_in_sec: float,
    ) -> None:
        if max_steps < 0:
            self._logger.warning("agent_loop_exhausted", stop_reason="too_many_steps")
            raise AgentLoopExhaustedError(AgentResult(stop_reason="too_many_steps", result=None))

        if self._get_costs_in_cents() >= max_costs_in_cents:
            self._logger.warning("agent_loop_exhausted", stop_reason="costs_too_high")
            raise AgentLoopExhaustedError(AgentResult(stop_reason="costs_too_high", result=None))

        if (time.perf_counter() - loop_start) >= max_time_in_sec:
            self._logger.warning("agent_loop_exhausted", stop_reason="timeout_exceeded")
            raise AgentLoopExhaustedError(AgentResult(stop_reason="timeout_exceeded", result=None))

    def _get_costs_in_cents(self) -> float:
        request_id = get_contextvars().get("request_id", "")
        usage = self._usage_tracker.snapshot(request_id)
        return usage.cost * 100 if usage else 0.0

    async def _handle_tool_call(
        self,
        messages: list[dict[str, Any]],
        result: Any,
        tool_calls: list[Any],
        tools: list[AgentTool[Any]],
    ) -> None:
        messages.append(result.choices[0].message)
        for tc in tool_calls:
            name = tc.function.name
            params = json.loads(tc.function.arguments)
            self._logger.info("executing_tool", tool_name=name)
            for tool in tools:
                if tool.get_name() == name:
                    tool_result = await tool.execute(params)
                    messages.append(
                        {
                            "tool_call_id": tc.id,
                            "role": "tool",
                            "name": name,
                            "content": tool_result,
                        }
                    )

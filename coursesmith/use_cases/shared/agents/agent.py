import json
from collections.abc import AsyncIterator
from typing import Any, TypeVar

import structlog
from pydantic import BaseModel

from coursesmith.use_cases.shared.agents.agent_tool import AgentTool
from coursesmith.use_cases.shared.ports.llm_port import LlmPort
from coursesmith.use_cases.shared.ports.prompts_port import PromptsPort

T = TypeVar("T", bound=BaseModel)

class AgentLoopExhaustedError(Exception):
    def __init__(self, message: str):
        super().__init__(message)

class Agent:
    def __init__(
        self,
        llm_port: LlmPort,
        prompts_port: PromptsPort,
    ):
        self._llm_port = llm_port
        self._prompts_port = prompts_port
        self._logger = structlog.get_logger()

    async def run(
        self,
        prompt_name: str,
        prompt_version: int,
        tools: list[AgentTool],
        prompt_params: dict[str, Any],
        response_format: type[T] | None = None,
        max_steps: int = 5,
    ) -> T | str | None:
        template = self._prompts_port.get_prompt(name=prompt_name, version=prompt_version)
        prompt = template.format(**prompt_params)
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

        budget = max_steps
        while max_steps > 0:
            max_steps -= 1
            result = await self._llm_port.complete(
                messages=messages,
                response_format=response_format,
                tools=[t.get_schema() for t in tools],
            )

            tool_calls = result.choices[0].message.tool_calls
            if tool_calls:
                await self._handle_tool_call(messages, result, tool_calls, tools)
            else:
                return result.choices[0].message.content

        self._logger.warning(
            "Agent loop has exhausted max_steps and, therefore, returns an empty object."
        )
        raise AgentLoopExhaustedError(f"max_steps of {budget} exhausted!")

    async def stream(
            self,
            prompt_name: str,
            prompt_version: int,
            tools: list[AgentTool],
            prompt_params: dict[str, Any],
            max_steps: int = 5,
    ) -> AsyncIterator[str]:

        template = self._prompts_port.get_prompt(name=prompt_name, version=prompt_version)
        prompt = template.format(**prompt_params)
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

        budget = max_steps
        while max_steps > 0:
            max_steps -= 1
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

        self._logger.warning(
            "Agent loop has exhausted max_steps and, therefore, returns an empty object."
        )
        raise AgentLoopExhaustedError(f"max_steps of {budget} exhausted!")

    async def _handle_tool_call(self, messages: list[dict[str, Any]], result, tool_calls, tools: list[AgentTool]):
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

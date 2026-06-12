import json
from collections.abc import AsyncGenerator
from typing import Any

import structlog

from coursesmith.use_cases.create_course_outline.models.course_outline import CourseOutline
from coursesmith.use_cases.create_course_outline.tools import (
    execute_tool,
    get_tools,
)
from coursesmith.use_cases.shared.ports.llm_port import LlmPort
from coursesmith.use_cases.shared.ports.prompts_port import PromptsPort


class CourseOutlineService:
    PROMPT_NAME = "course_outline"

    def __init__(
        self,
        llm_port: LlmPort,
        prompts_port: PromptsPort,
        prompt_version: int,
    ):
        self._llm_port = llm_port
        self._prompts_port = prompts_port
        self._prompt = prompts_port.get_prompt(name=self.PROMPT_NAME, version=prompt_version)
        self._logger = structlog.get_logger()

    async def create(self, topic: str) -> CourseOutline:
        prompt = self._prompt.format(topic=topic)
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        tools = get_tools()
        max_steps = 5
        while max_steps > 0:
            max_steps -= 1
            result = await self._llm_port.complete(
                messages=messages, response_format=CourseOutline, tools=tools
            )

            tool_calls = result.choices[0].message.tool_calls
            if tool_calls:
                messages.append(result.choices[0].message)
                for tc in tool_calls:
                    name = tc.function.name
                    params = json.loads(tc.function.arguments)
                    self._logger.info("executing_tool", tool_name=name)
                    tool_result = await execute_tool(
                        name=name,
                        llm_port=self._llm_port,
                        prompts_port=self._prompts_port,
                        **params,
                    )
                    messages.append(
                        {
                            "tool_call_id": tc.id,
                            "role": "tool",
                            "name": name,
                            "content": tool_result,
                        }
                    )
            else:
                return CourseOutline.model_validate_json(result.choices[0].message.content)

        self._logger.warning(
            "Agent loop has exhausted max_steps and, therefore, returns an empty object."
        )
        return CourseOutline(title="n/a", day_items=[])

    async def create_stream(self, topic: str) -> AsyncGenerator[str, None]:
        prompt = self._prompt.format(topic=topic)
        messages = [{"role": "user", "content": prompt}]
        async for chunk in self._llm_port.stream(messages=messages):
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

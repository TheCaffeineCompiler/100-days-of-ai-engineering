import json
from collections.abc import AsyncGenerator

import structlog

from coursesmith.use_cases.create_course_outline.models.course_outline import CourseOutline
from coursesmith.use_cases.create_course_outline.tools.get_current_time_tool import (
    get_current_time_schema,
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
        self._prompt = prompts_port.get_prompt(name=self.PROMPT_NAME, version=prompt_version)
        self._logger = structlog.get_logger()

    async def create(self, topic: str) -> CourseOutline:
        prompt = self._prompt.format(topic=topic)
        messages = [{"role": "user", "content": prompt}]
        result = await self._llm_port.complete(
            messages=messages, response_format=CourseOutline, tools=[get_current_time_schema()]
        )
        tool_calls = result.choices[0].message.tool_calls
        if tool_calls:
            for tc in tool_calls:
                name = tc.function.name
                params = json.loads(tc.function.arguments)
                self._logger.info("call_function", tool_name=name, tool_params=params)
            return CourseOutline(title="n/a", day_items=[])
        return CourseOutline.model_validate_json(json_data=result.choices[0].message.content or "")

    async def create_stream(self, topic: str) -> AsyncGenerator[str, None]:
        prompt = self._prompt.format(topic=topic)
        messages = [{"role": "user", "content": prompt}]
        async for chunk in self._llm_port.stream(messages=messages):
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

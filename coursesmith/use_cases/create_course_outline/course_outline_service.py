from collections.abc import AsyncGenerator
from typing import Any, cast

import structlog

from coursesmith.use_cases.create_course_outline.models.course_outline import CourseOutline
from coursesmith.use_cases.shared.agents.agent import Agent
from coursesmith.use_cases.shared.agents.agent_tool import AgentTool


class CourseOutlineService:
    def __init__(
        self,
        agent: Agent,
        tools: list[AgentTool[Any]],
        prompt_version: int,
    ):
        self._agent = agent
        self._tools = tools
        self._prompt_name = "course_outline"
        self._prompt_version = prompt_version
        self._logger = structlog.get_logger()

    async def create(self, topic: str) -> CourseOutline:
        params = {"topic": topic}
        agent_result = await self._agent.run(
            prompt_name=self._prompt_name,
            prompt_version=self._prompt_version,
            tools=self._tools,
            prompt_params=params,
            response_format=CourseOutline,
        )
        return CourseOutline.model_validate_json(cast(str, agent_result.result))

    async def create_stream(self, topic: str) -> AsyncGenerator[str, None]:
        params = {"topic": topic}
        async for token in self._agent.stream(
            prompt_name=self._prompt_name,
            prompt_version=self._prompt_version,
            tools=self._tools,
            prompt_params=params,
        ):
            yield token

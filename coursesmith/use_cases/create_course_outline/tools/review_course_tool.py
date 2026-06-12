from typing import Any

from pydantic import BaseModel, Field

from coursesmith.use_cases.shared.agents.agent_tool import AgentTool
from coursesmith.use_cases.shared.ports.llm_port import LlmPort
from coursesmith.use_cases.shared.ports.prompts_port import PromptsPort


class ReviewCourseParams(BaseModel):
    title: str
    content: str = Field(description="joined list of day items")


class ReviewCourseTool(AgentTool[ReviewCourseParams]):

    def __init__(
        self,
        llm_port: LlmPort,
        prompts_port: PromptsPort,
        prompts_name: str,
        prompts_version: int,
        response_type: type[BaseModel] | None = None,
    ):
        self._llm_port = llm_port
        self._prompts_port = prompts_port
        self._prompts_name = prompts_name
        self._prompts_version = prompts_version
        self._response_type = response_type

    def name(self) -> str:
        return "review_course"

    def description(self) -> str:
        return "Call this function to improve the title and schedule of a given course"

    def params_cls(self) -> type[ReviewCourseParams]:
        return ReviewCourseParams

    async def _execute(self, params: ReviewCourseParams) -> Any:
        template = self._prompts_port.get_prompt(
            name=self._prompts_name, version=self._prompts_version
        )
        prompt = template.format(title=params.title, content=params.content)
        result = await self._llm_port.complete(
            messages=[{"role": "user", "content": prompt}],
            response_format=self._response_type,
        )
        return result.choices[0].message.content

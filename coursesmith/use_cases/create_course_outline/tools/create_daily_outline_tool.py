from typing import Any

from coursesmith.use_cases.create_course_outline.models.course_outline import Outlines, Schedule
from coursesmith.use_cases.shared.agents.agent_tool import AgentTool
from coursesmith.use_cases.shared.ports.llm_port import LlmPort
from coursesmith.use_cases.shared.ports.prompts_port import PromptsPort


class CreateDailyOutlineTool(AgentTool[Schedule]):
    def __init__(
        self,
        llm_port: LlmPort,
        prompts_port: PromptsPort,
        prompts_name: str,
        prompts_version: int,
    ):
        self._llm_port = llm_port
        self._prompts_port = prompts_port
        self._prompts_name = prompts_name
        self._prompts_version = prompts_version

    def name(self) -> str:
        return "create_daily_outline"

    def description(self) -> str:
        return "Call the function to create an outline for each day"

    def params_cls(self) -> type[Schedule]:
        return Schedule

    async def _execute(self, params: Schedule) -> Any:
        template = self._prompts_port.get_prompt(
            name=self._prompts_name, version=self._prompts_version
        )
        days = [f"Day {d.day}: {d.objective}" for d in params.day_items]
        prompt = template.format(schedule="\n* ".join(days))
        result = await self._llm_port.complete(
            messages=[{"role": "user", "content": prompt}],
            response_format=Outlines,
        )
        return result.choices[0].message.content

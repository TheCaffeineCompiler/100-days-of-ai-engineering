from typing import Any

from pydantic import BaseModel

from coursesmith.use_cases.shared.agents.agent_tool import AgentTool
from coursesmith.use_cases.shared.ports.llm_port import LlmPort
from coursesmith.use_cases.shared.ports.prompts_port import PromptsPort


class CreateTitleParams(BaseModel):
    topic: str


class CreateTitleTool(AgentTool[CreateTitleParams]):
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
        return "create_title"

    def description(self) -> str:
        return "Call this function to create an attractive course title for a given topic"

    def params_cls(self) -> type[CreateTitleParams]:
        return CreateTitleParams

    async def _execute(self, params: CreateTitleParams) -> Any:
        template = self._prompts_port.get_prompt(
            name=self._prompts_name, version=self._prompts_version
        )
        prompt = template.format(topic=params.topic)
        result = await self._llm_port.complete(
            messages=[{"role": "user", "content": prompt}],
            response_format=None,
        )
        return result.choices[0].message.content

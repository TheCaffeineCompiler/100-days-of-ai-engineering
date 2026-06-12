from typing import Any

from pydantic import BaseModel

from coursesmith.settings import settings
from coursesmith.use_cases.shared.ports.llm_port import LlmPort
from coursesmith.use_cases.shared.ports.prompts_port import PromptsPort

PROMPT_NAME = "course_schedule"


class CreateScheduleParams(BaseModel):
    title: str


def create_schedule_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "create_schedule",
            "description": "Call this function to create a detailed schedule for a given course title",
            "parameters": CreateScheduleParams.model_json_schema(),
        },
    }


async def create_schedule(
    llm_port: LlmPort,
    prompts_port: PromptsPort,
    request: CreateScheduleParams,
) -> Any:
    template = prompts_port.get_prompt(
        name=PROMPT_NAME, version=settings.create_schedule_prompt_version
    )
    prompt = template.format(title=request.title)
    result = await llm_port.complete(
        messages=[{"role": "user", "content": prompt}],
        response_format=None,
    )
    return result.choices[0].message.content

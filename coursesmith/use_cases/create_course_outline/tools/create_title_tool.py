from typing import Any

from pydantic import BaseModel

from coursesmith.settings import settings
from coursesmith.use_cases.shared.ports.llm_port import LlmPort
from coursesmith.use_cases.shared.ports.prompts_port import PromptsPort

PROMPT_NAME = "course_title"


class CreateTitleParams(BaseModel):
    topic: str


def create_title_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "create_title",
            "description": "Call this function to create an attractive course title for a given topic",
            "parameters": CreateTitleParams.model_json_schema(),
        },
    }


async def create_title(
    llm_port: LlmPort,
    prompts_port: PromptsPort,
    request: CreateTitleParams,
) -> Any:
    template = prompts_port.get_prompt(
        name=PROMPT_NAME, version=settings.create_title_prompt_version
    )
    prompt = template.format(topic=request.topic)
    result = await llm_port.complete(
        messages=[{"role": "user", "content": prompt}],
        response_format=None,
    )
    return result.choices[0].message.content

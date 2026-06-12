from typing import Any

from pydantic import BaseModel

from coursesmith.settings import settings
from coursesmith.use_cases.create_course_outline.models.course_outline import CourseOutline, DayItem
from coursesmith.use_cases.shared.ports.llm_port import LlmPort
from coursesmith.use_cases.shared.ports.prompts_port import PromptsPort

PROMPT_NAME = "review_course"


class ReviewCourseParams(BaseModel):
    title: str
    day_items: list[DayItem]


def review_course_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "review_course",
            "description": "Call this function to improve the title and schedule of a given course",
            "parameters": ReviewCourseParams.model_json_schema(),
        },
    }


async def review_course(
    llm_port: LlmPort,
    prompts_port: PromptsPort,
    request: ReviewCourseParams,
) -> Any:
    template = prompts_port.get_prompt(
        name=PROMPT_NAME, version=settings.review_course_prompt_version
    )
    content = [d.model_dump_json() for d in request.day_items]
    prompt = template.format(title=request.title, content="\n".join(content))
    result = await llm_port.complete(
        messages=[{"role": "user", "content": prompt}],
        response_format=CourseOutline,
    )
    return result.choices[0].message.content

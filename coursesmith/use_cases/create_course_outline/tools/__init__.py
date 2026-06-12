from typing import Any

from coursesmith.use_cases.create_course_outline.tools.create_schedule_tool import (
    CreateScheduleParams,
    create_schedule,
    create_schedule_schema,
)
from coursesmith.use_cases.create_course_outline.tools.create_title_tool import (
    CreateTitleParams,
    create_title,
    create_title_schema,
)
from coursesmith.use_cases.create_course_outline.tools.review_course_tool import (
    ReviewCourseParams,
    review_course,
    review_course_schema,
)
from coursesmith.use_cases.shared.ports.llm_port import LlmPort
from coursesmith.use_cases.shared.ports.prompts_port import PromptsPort


def get_tools() -> list[dict[str, Any]]:
    return [
        create_title_schema(),
        create_schedule_schema(),
        review_course_schema(),
    ]


async def execute_tool(
    name: str, llm_port: LlmPort, prompts_port: PromptsPort, **kwargs: Any
) -> Any:
    try:
        if name == "create_title":
            return await create_title(
                llm_port=llm_port,
                prompts_port=prompts_port,
                request=CreateTitleParams.model_validate(kwargs),
            )
        if name == "create_schedule":
            return await create_schedule(
                llm_port=llm_port,
                prompts_port=prompts_port,
                request=CreateScheduleParams.model_validate(kwargs),
            )
        if name == "review_course":
            return await review_course(
                llm_port=llm_port,
                prompts_port=prompts_port,
                request=ReviewCourseParams.model_validate(kwargs),
            )
        return f"Unknown tool: {name}"
    except Exception as e:
        return f"Error while executing tool: {e}"

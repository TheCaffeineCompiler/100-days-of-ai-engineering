from functools import lru_cache

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from coursesmith import RESOURCES_DIR
from coursesmith.infrastructure.shared.adapters.prompts_adapter import PromptsAdapter
from coursesmith.settings import Settings
from coursesmith.use_cases.create_course_outline.course_outline_service import CourseOutlineService
from coursesmith.use_cases.create_course_outline.models.course_outline import CourseOutline

router = APIRouter(prefix="/courses", tags=["courses"])


@lru_cache
def get_service() -> CourseOutlineService:
    settings = Settings()
    prompts_port = PromptsAdapter(base_path=RESOURCES_DIR)
    return CourseOutlineService(
        model=settings.litellm_model,
        api_key=settings.litellm_api_key,
        prompts_port=prompts_port,
        prompt_version=settings.course_outline_prompt_version,
    )


class CreateCourseOutlineRequest(BaseModel):
    topic: str


@router.post("", response_model=CourseOutline)
async def create_course_outline(
    request: CreateCourseOutlineRequest,
    service: CourseOutlineService = Depends(get_service),
) -> CourseOutline:
    return await service.create(topic=request.topic)

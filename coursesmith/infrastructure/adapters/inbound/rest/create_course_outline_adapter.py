from collections.abc import AsyncIterable

from fastapi import APIRouter, Depends, Response, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from coursesmith.composition import get_service, get_usage_tracker
from coursesmith.infrastructure.shared.observability.usage_tracker import (
    UsageModel,
    UsageTracker,
)
from coursesmith.use_cases.create_course_outline.course_outline_service import CourseOutlineService
from coursesmith.use_cases.create_course_outline.models.course_outline import CourseOutline

router = APIRouter(prefix="/courses", tags=["courses"])


class CreateCourseOutlineRequest(BaseModel):
    topic: str


@router.post("", response_model=CourseOutline)
async def create_course_outline(
    request: CreateCourseOutlineRequest,
    service: CourseOutlineService = Depends(get_service),
) -> CourseOutline:
    return await service.create(topic=request.topic)


@router.post("/stream", response_class=EventSourceResponse)
async def stream_create_course_outline(
    request: CreateCourseOutlineRequest,
    service: CourseOutlineService = Depends(get_service),
) -> AsyncIterable[ServerSentEvent]:
    words = service.create_stream(topic=request.topic)
    async for word in words:
        yield ServerSentEvent(data=word, event="token")
    yield ServerSentEvent(raw_data="[DONE]", event="done")


@router.get("/usage/{request_id}")
async def get_usage_per_request(
    request_id: str, response: Response, usage_tracker: UsageTracker = Depends(get_usage_tracker)
) -> UsageModel | None:
    usage = usage_tracker.snapshot(request_id)
    response.status_code = status.HTTP_200_OK if usage else status.HTTP_404_NOT_FOUND
    return usage

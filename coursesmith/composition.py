"""Composition root.

Lazy module-level singletons. Each component is constructed on first
access via a `get_*` accessor and cached in a module-level `_x: T | None`
slot. Routes import the `get_*` functions and use them as `Depends(...)`
markers — that lets FastAPI swap them out via `app.dependency_overrides`
in tests.
"""

from fastapi import Depends

from coursesmith import RESOURCES_DIR
from coursesmith.infrastructure.shared.adapters.outbound.lite_llm_adapter import LiteLlmAdapter
from coursesmith.infrastructure.shared.adapters.outbound.prompts_adapter import PromptsAdapter
from coursesmith.infrastructure.shared.observability.usage_tracker import UsageTracker
from coursesmith.settings import settings
from coursesmith.use_cases.create_course_outline.course_outline_service import CourseOutlineService
from coursesmith.use_cases.create_course_outline.models.course_outline import CourseOutline
from coursesmith.use_cases.create_course_outline.tools.create_schedule_tool import (
    CreateScheduleTool,
)
from coursesmith.use_cases.create_course_outline.tools.create_title_tool import CreateTitleTool
from coursesmith.use_cases.create_course_outline.tools.review_course_tool import ReviewCourseTool
from coursesmith.use_cases.shared.agents.agent import Agent
from coursesmith.use_cases.shared.agents.agent_tool import AgentTool
from coursesmith.use_cases.shared.ports.llm_port import LlmPort
from coursesmith.use_cases.shared.ports.prompts_port import PromptsPort

_usage_tracker: UsageTracker | None = None
_llm_port: LlmPort | None = None
_prompts_port: PromptsPort | None = None
_agent: Agent | None = None
_service: CourseOutlineService | None = None

_create_title_tool: CreateTitleTool | None = None
_create_schedule_tool: CreateScheduleTool | None = None
_review_course_tool: ReviewCourseTool | None = None


def get_usage_tracker() -> UsageTracker:
    global _usage_tracker
    if _usage_tracker is None:
        _usage_tracker = UsageTracker()
    return _usage_tracker


def get_llm_port(usage_tracker: UsageTracker = Depends(get_usage_tracker)) -> LlmPort:
    global _llm_port
    if _llm_port is None:
        _llm_port = LiteLlmAdapter(
            usage_tracker=usage_tracker,
            model=settings.litellm_model,
            api_key=settings.litellm_api_key,
            retries=settings.litellm_retries,
            timeout=settings.litellm_timeout,
        )
    return _llm_port


def get_prompts_port() -> PromptsPort:
    global _prompts_port
    if _prompts_port is None:
        _prompts_port = PromptsAdapter(base_path=RESOURCES_DIR)
    return _prompts_port


def get_agent(
    llm_port: LlmPort = Depends(get_llm_port), prompts_port: PromptsPort = Depends(get_prompts_port)
) -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent(llm_port=llm_port, prompts_port=prompts_port)
    return _agent


def get_create_title_tool(
    llm_port: LlmPort = Depends(get_llm_port),
    prompts_port: PromptsPort = Depends(get_prompts_port),
) -> CreateTitleTool:
    global _create_title_tool
    if _create_title_tool is None:
        _create_title_tool = CreateTitleTool(
            llm_port=llm_port,
            prompts_port=prompts_port,
            prompts_name="course_title",
            prompts_version=settings.create_title_prompt_version,
        )
    return _create_title_tool


def get_create_schedule_tool(
    llm_port: LlmPort = Depends(get_llm_port),
    prompts_port: PromptsPort = Depends(get_prompts_port),
) -> CreateScheduleTool:
    global _create_schedule_tool
    if _create_schedule_tool is None:
        _create_schedule_tool = CreateScheduleTool(
            llm_port=llm_port,
            prompts_port=prompts_port,
            prompts_name="course_schedule",
            prompts_version=settings.create_schedule_prompt_version,
        )
    return _create_schedule_tool


def get_review_course_tool(
    llm_port: LlmPort = Depends(get_llm_port),
    prompts_port: PromptsPort = Depends(get_prompts_port),
) -> ReviewCourseTool:
    global _review_course_tool
    if _review_course_tool is None:
        _review_course_tool = ReviewCourseTool(
            llm_port=llm_port,
            prompts_port=prompts_port,
            prompts_name="review_course",
            prompts_version=settings.review_course_prompt_version,
            response_type=CourseOutline,
        )
    return _review_course_tool


def get_service_tools(
    create_title_tool: CreateTitleTool = Depends(get_create_title_tool),
    create_schedule_tool: CreateScheduleTool = Depends(get_create_schedule_tool),
    review_course_tool: ReviewCourseTool = Depends(get_review_course_tool),
) -> list[AgentTool]:
    return [create_title_tool, create_schedule_tool, review_course_tool]


def get_service(
    agent: Agent = Depends(get_agent),
    tools: list[AgentTool] = Depends(get_service_tools),
) -> CourseOutlineService:
    global _service
    if _service is None:
        _service = CourseOutlineService(
            agent=agent,
            tools=tools,
            prompt_version=settings.course_outline_prompt_version,
        )
    return _service

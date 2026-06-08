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
from coursesmith.use_cases.shared.ports.llm_port import LlmPort
from coursesmith.use_cases.shared.ports.prompts_port import PromptsPort

_usage_tracker: UsageTracker | None = None
_llm_port: LlmPort | None = None
_prompts_port: PromptsPort | None = None
_service: CourseOutlineService | None = None


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


def get_service(
    prompts_port: PromptsPort = Depends(get_prompts_port),
    llm_port: LlmPort = Depends(get_llm_port),
) -> CourseOutlineService:
    global _service
    if _service is None:
        _service = CourseOutlineService(
            llm_port=llm_port,
            prompts_port=prompts_port,
            prompt_version=settings.course_outline_prompt_version,
        )
    return _service

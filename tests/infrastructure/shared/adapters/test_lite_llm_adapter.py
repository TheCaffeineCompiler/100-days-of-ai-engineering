import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from litellm.exceptions import RateLimitError, Timeout
from pydantic import BaseModel

from coursesmith.infrastructure.shared.adapters.lite_llm_adapter import LiteLlmAdapter
from coursesmith.infrastructure.shared.utils.usage_tracker import UsageTracker
from coursesmith.use_cases.shared.ports.llm_port import LlmRateLimitError, LlmTimeoutError


class _Schema(BaseModel):
    pass


def _make_adapter() -> LiteLlmAdapter:
    """Construct an adapter with throwaway config; tests patch `_router` directly."""
    return LiteLlmAdapter(
        usage_tracker=UsageTracker(),
        model="openai/gpt-test",
        api_key="sk-test",
        retries=0,
        timeout=1,
    )


def _timeout() -> Timeout:
    return Timeout(message="timed out", model="openai/gpt-test", llm_provider="openai")


def _rate_limit() -> RateLimitError:
    return RateLimitError(message="429", llm_provider="openai", model="openai/gpt-test")


async def _raising_stream(exc: Exception) -> AsyncIterator[object]:
    """Yield one chunk then raise — mirrors a stream that fails mid-iteration."""
    yield object()
    raise exc


def test_complete_translates_timeout_to_llm_timeout_error():
    adapter = _make_adapter()
    adapter._router.acompletion = AsyncMock(side_effect=_timeout())  # type: ignore[method-assign]

    with pytest.raises(LlmTimeoutError):
        asyncio.run(adapter.complete(messages=[], response_format=_Schema))


def test_complete_translates_rate_limit_to_llm_rate_limit_error():
    adapter = _make_adapter()
    adapter._router.acompletion = AsyncMock(side_effect=_rate_limit())  # type: ignore[method-assign]

    with pytest.raises(LlmRateLimitError):
        asyncio.run(adapter.complete(messages=[], response_format=_Schema))


def test_stream_translates_timeout_mid_iteration():
    """Streaming errors fire during `async for`, not at the initial await.
    The adapter must wrap the iteration so they're still translated."""
    adapter = _make_adapter()
    adapter._router.acompletion = AsyncMock(return_value=_raising_stream(_timeout()))  # type: ignore[method-assign]

    async def _drain() -> None:
        async for _ in adapter.stream(messages=[]):
            pass

    with pytest.raises(LlmTimeoutError):
        asyncio.run(_drain())


def test_stream_translates_rate_limit_mid_iteration():
    adapter = _make_adapter()
    adapter._router.acompletion = AsyncMock(return_value=_raising_stream(_rate_limit()))  # type: ignore[method-assign]

    async def _drain() -> None:
        async for _ in adapter.stream(messages=[]):
            pass

    with pytest.raises(LlmRateLimitError):
        asyncio.run(_drain())

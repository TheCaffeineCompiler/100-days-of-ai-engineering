from collections.abc import AsyncIterator
from typing import Any, cast

from litellm.exceptions import RateLimitError, Timeout
from litellm.router import Router

from coursesmith.use_cases.shared.ports.llm_port import (
    LlmPort,
    LlmRateLimitError,
    LlmTimeoutError,
    T,
)


class LiteLlmAdapter(LlmPort):
    def __init__(
        self,
        model: str,
        api_key: str,
        retries: int,
        timeout: int,
    ):
        self._model = model
        self._timeout = timeout
        self._router = Router(
            model_list=[
                {
                    "model_name": model,
                    "litellm_params": {
                        "model": model,
                        "api_key": api_key,
                    },
                }
            ],
            num_retries=retries,
            timeout=timeout,
        )

    async def complete(self, messages: list[dict[str, str]], response_format: type[T]) -> Any:
        try:
            return await self._router.acompletion(
                model=self._model,
                messages=cast(Any, messages),
                response_format=response_format,
            )
        except Timeout as e:
            raise LlmTimeoutError(f"LLM call timed out after {self._timeout}s") from e
        except RateLimitError as e:
            raise LlmRateLimitError("Hit rate limit. Please try again later.") from e

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[Any]:
        try:
            result = await self._router.acompletion(
                model=self._model,
                messages=cast(Any, messages),
                stream=True,
            )
            async for chunk in result:
                yield chunk
        except Timeout as e:
            raise LlmTimeoutError(f"LLM call timed out after {self._timeout}s") from e
        except RateLimitError as e:
            raise LlmRateLimitError("Hit rate limit. Please try again later.") from e

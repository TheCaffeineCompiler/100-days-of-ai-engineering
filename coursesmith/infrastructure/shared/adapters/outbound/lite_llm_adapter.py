from collections.abc import AsyncIterator
from typing import Any, cast

import structlog
from litellm import completion_cost, cost_per_token, stream_chunk_builder, token_counter
from litellm.exceptions import RateLimitError, Timeout
from litellm.router import Router
from litellm.types.utils import ModelResponse

from coursesmith.infrastructure.shared.observability.usage_tracker import UsageTracker
from coursesmith.use_cases.shared.ports.llm_port import (
    LlmPort,
    LlmRateLimitError,
    LlmTimeoutError,
    T,
)


class LiteLlmAdapter(LlmPort):
    def __init__(
        self,
        usage_tracker: UsageTracker,
        model: str,
        api_key: str,
        retries: int,
        timeout: int,
    ):
        self._logger = structlog.get_logger()
        self._usage_tracker = usage_tracker
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

    async def complete(
        self,
        messages: list[dict[str, str]],
        response_format: type[T] | None,
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        try:
            result = await self._router.acompletion(
                model=self._model,
                messages=cast(Any, messages),
                response_format=response_format,
                tools=tools or [],
            )
            await self._log_llm_costs(messages, result)
            return result
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
                stream_options={"include_usage": True},
            )
            chunks = []
            async for chunk in result:
                chunks.append(chunk)
                yield chunk
            final_result = stream_chunk_builder(chunks=chunks, messages=messages)
            if isinstance(final_result, ModelResponse):
                await self._log_llm_costs(messages, final_result)
        except Timeout as e:
            raise LlmTimeoutError(f"LLM call timed out after {self._timeout}s") from e
        except RateLimitError as e:
            raise LlmRateLimitError("Hit rate limit. Please try again later.") from e

    async def _log_llm_costs(self, messages: list[dict[str, str]], result: ModelResponse) -> None:
        tokens_prompt = token_counter(model=self._model, messages=messages)
        tokens_completion = token_counter(model=self._model, messages=[result.choices[0].message])
        token_cost_prompt, token_cost_completion = cost_per_token(
            model=self._model,
            prompt_tokens=tokens_prompt,
            completion_tokens=tokens_completion,
        )
        cost_completion = completion_cost(result)
        self._logger.info(
            "llm_costs_calculated",
            completion_cost=cost_completion,
            tokens_prompt=tokens_prompt,
            token_cost_prompt=token_cost_prompt,
            tokens_completion=tokens_completion,
            token_cost_completion=token_cost_completion,
        )
        self._usage_tracker.record(
            prompt=tokens_prompt, completion=tokens_completion, cost=cost_completion
        )

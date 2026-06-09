from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LlmPort(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        response_format: type[T],
        tools: list[dict[str, Any]] | None = None,
    ) -> Any: ...

    @abstractmethod
    def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[Any]: ...


class LlmError(Exception):
    pass


class LlmTimeoutError(LlmError):
    pass


class LlmRateLimitError(LlmError):
    pass

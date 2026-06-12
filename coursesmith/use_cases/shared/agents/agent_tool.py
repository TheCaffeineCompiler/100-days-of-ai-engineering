from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

TParams = TypeVar("TParams", bound=BaseModel)

class AgentTool(ABC, Generic[TParams]):
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def params_cls(self) -> type[TParams]: ...

    @abstractmethod
    async def _execute(self, params: TParams) -> Any: ...

    def get_name(self) -> str:
        return self.name()

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": self.params_cls().model_json_schema(),
            },
        }

    async def execute(self, args: dict[str, Any]) -> Any:
        return await self._execute(self.params_cls().model_validate(args))


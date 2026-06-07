from functools import lru_cache

from pydantic import BaseModel
from structlog.contextvars import get_contextvars


@lru_cache
def get_usage_tracker() -> "UsageTracker":
    return UsageTracker()


class UsageModel(BaseModel):
    prompt: int
    completion: int
    cost: float


class UsageTracker:
    def __init__(self) -> None:
        self._state: dict[str, UsageModel] = {}

    def record(self, prompt: int, completion: int, cost: float) -> None:
        request_id = get_contextvars().get("request_id", None)
        if request_id:
            current_state = self._state.get(request_id, None)
            if current_state:
                current_state.prompt += prompt
                current_state.completion += completion
                current_state.cost += cost
            else:
                self._state[request_id] = UsageModel(
                    prompt=prompt, completion=completion, cost=cost
                )

    def snapshot(self, request_id: str) -> UsageModel | None:
        return self._state.get(request_id, None)

from pydantic import BaseModel
from structlog.contextvars import get_contextvars


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
                new_state = current_state.model_copy(
                    update={
                        "prompt": current_state.prompt + prompt,
                        "completion": current_state.completion + completion,
                        "cost": current_state.cost + cost,
                    }
                )
            else:
                new_state = UsageModel(prompt=prompt, completion=completion, cost=cost)
            self._state[request_id] = new_state

    def snapshot(self, request_id: str) -> UsageModel | None:
        return self._state.get(request_id, None)

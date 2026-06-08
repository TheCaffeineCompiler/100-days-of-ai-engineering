from datetime import datetime
from typing import Any

from pydantic import BaseModel


class GetCurrentTimeParams(BaseModel):
    pattern: str = "%Y-%m-%dT%H:%M:%S"


def get_current_time_schema() -> dict[str, Any]:
    params = GetCurrentTimeParams.model_json_schema()
    return {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Call this tool to get the current time formatted with the given strftime pattern.",
            "parameters": params,
        },
    }


def get_current_time(pattern: str = "%Y-%m-%dT%H:%M:%S") -> str:
    return datetime.now().strftime(format=pattern)

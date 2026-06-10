from typing import Any

from coursesmith.use_cases.create_course_outline.tools.get_current_time_tool import (
    get_current_time,
    get_current_time_schema,
)


def get_tools() -> list[dict[str, Any]]:
    return [get_current_time_schema()]


def execute_tool(name: str, **kwargs: Any) -> Any:
    if name == "get_current_time":
        try:
            return get_current_time(**kwargs)
        except Exception as e:
            return f"Error while executing tool: {e}"
    return f"Unknown tool: {name}"

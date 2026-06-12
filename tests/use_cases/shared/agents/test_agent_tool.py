"""Tests for the AgentTool ABC template-method behavior.

The ABC owns two pieces of behavior the subclasses don't write themselves:
- `get_schema()` builds the OpenAI tool-schema dict from name/description/params_cls
- `execute(args)` validates `args` against `params_cls` and dispatches to `_execute(params)`
"""

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from coursesmith.use_cases.shared.agents.agent_tool import AgentTool


class _ProbeParams(BaseModel):
    topic: str
    count: int = 1


class _ProbeTool(AgentTool[_ProbeParams]):
    """Records the validated params object that `_execute` received."""

    def __init__(self) -> None:
        self.received: _ProbeParams | None = None

    def name(self) -> str:
        return "probe"

    def description(self) -> str:
        return "A probe tool used in tests."

    def params_cls(self) -> type[_ProbeParams]:
        return _ProbeParams

    async def _execute(self, params: _ProbeParams) -> Any:
        self.received = params
        return f"got {params.topic} x{params.count}"


def test_get_schema_returns_openai_tool_shape():
    schema = _ProbeTool().get_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "probe"
    assert schema["function"]["description"] == "A probe tool used in tests."
    # parameters block is the params model's JSON schema, not a hand-rolled dict.
    assert schema["function"]["parameters"] == _ProbeParams.model_json_schema()


def test_get_name_proxies_to_name():
    assert _ProbeTool().get_name() == "probe"


def test_execute_validates_args_into_params_model():
    tool = _ProbeTool()
    result = asyncio.run(tool.execute({"topic": "git", "count": 3}))
    assert result == "got git x3"
    assert tool.received == _ProbeParams(topic="git", count=3)


def test_execute_applies_field_defaults():
    """Missing optional field falls back to the model's default, not to KeyError."""
    tool = _ProbeTool()
    asyncio.run(tool.execute({"topic": "git"}))
    assert tool.received == _ProbeParams(topic="git", count=1)


def test_execute_raises_validation_error_on_missing_required_field():
    """Boundary validation: the LLM sending malformed args must surface as a pydantic
    error, not as a silent format-string KeyError inside `_execute`."""
    with pytest.raises(ValidationError):
        asyncio.run(_ProbeTool().execute({"count": 3}))


def test_execute_raises_validation_error_on_wrong_type():
    with pytest.raises(ValidationError):
        asyncio.run(_ProbeTool().execute({"topic": "git", "count": "not-an-int"}))

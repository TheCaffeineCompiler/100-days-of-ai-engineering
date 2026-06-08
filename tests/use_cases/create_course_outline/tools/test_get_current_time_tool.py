from datetime import datetime

from coursesmith.use_cases.create_course_outline.tools.get_current_time_tool import (
    GetCurrentTimeParams,
    get_current_time,
    get_current_time_schema,
)


def test_schema_top_level_shape():
    schema = get_current_time_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "get_current_time"
    assert "description" in schema["function"]


def test_schema_parameters_are_a_valid_json_schema_object():
    params = get_current_time_schema()["function"]["parameters"]
    assert params["type"] == "object"
    assert "pattern" in params["properties"]
    assert params["properties"]["pattern"]["type"] == "string"


def test_schema_exposes_pattern_default_to_the_model():
    params = get_current_time_schema()["function"]["parameters"]
    assert params["properties"]["pattern"]["default"] == GetCurrentTimeParams().pattern


def test_function_and_model_defaults_match():
    # Guards against silent drift between the two hard-coded defaults.
    import inspect

    func_default = inspect.signature(get_current_time).parameters["pattern"].default
    assert func_default == GetCurrentTimeParams().pattern


def test_get_current_time_round_trips_with_default_pattern():
    result = get_current_time()
    parsed = datetime.strptime(result, GetCurrentTimeParams().pattern)
    assert (datetime.now() - parsed).total_seconds() < 5


def test_get_current_time_respects_custom_pattern():
    result = get_current_time(pattern="%Y-%m-%d")
    datetime.strptime(result, "%Y-%m-%d")  # raises if format wrong
    assert len(result) == 10

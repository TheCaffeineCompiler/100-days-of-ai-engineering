from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from coursesmith.app import app
from coursesmith.infrastructure.adapters.inbound.rest.create_course_outline_adapter import (
    get_service,
)
from coursesmith.use_cases.create_course_outline.models.course_outline import CourseOutline


def test_post_courses_returns_course_outline_json():
    outline = CourseOutline(title="x", day_items=[], daily_outlines=[], daily_quizzes=[])
    fake = SimpleNamespace(create=AsyncMock(return_value=outline))
    app.dependency_overrides[get_service] = lambda: fake
    try:
        with TestClient(app) as client:
            resp = client.post("/courses", json={"topic": "AI engineering"})
        assert resp.status_code == 200
        assert resp.json() == {
            "title": "x",
            "day_items": [],
            "daily_outlines": [],
            "daily_quizzes": [],
        }
    finally:
        app.dependency_overrides.clear()

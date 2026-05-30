from pydantic import BaseModel


class DayItem(BaseModel):
    day: int
    content: str
    tasks: list[str]


class CourseOutline(BaseModel):
    title: str
    day_items: list[DayItem]

from pydantic import BaseModel


class DayItem(BaseModel):
    day: int
    objective: str


class Schedule(BaseModel):
    day_items: list[DayItem]


class Outlines(BaseModel):
    daily_outlines: list[str]


class QuizQuestion(BaseModel):
    question: str
    answer_options: list[str]
    correct_answer: int


class DailyQuiz(BaseModel):
    questions: list[QuizQuestion]


class Quiz(BaseModel):
    daily_quizzes: list[DailyQuiz]


class CourseOutline(BaseModel):
    title: str
    day_items: list[DayItem]
    daily_outlines: list[str]
    daily_quizzes: list[DailyQuiz]

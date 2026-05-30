from litellm import completion

from coursesmith.use_cases.create_course_outline.models.course_outline import CourseOutline

_prompt = """
Please create a course outline spanning multiple days for the following topic:

{topic}

Each day should have an objective and a list of tasks to be completed.
"""


class CourseOutlineService:
    def __init__(
        self,
        model: str,
        api_key: str,
    ):
        self._model = model
        self._api_key = api_key

    def create(self, title: str) -> CourseOutline:
        prompt = _prompt.format(topic=title)
        messages = [{"role": "user", "content": prompt}]
        result = completion(
            messages=messages,
            model=self._model,
            api_key=self._api_key,
            response_format=CourseOutline,
        )
        return CourseOutline.model_validate_json(json_data=result.choices[0].message.content or "")

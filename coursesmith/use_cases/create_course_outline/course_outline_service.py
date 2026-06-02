from collections.abc import AsyncGenerator

from litellm import acompletion

from coursesmith.use_cases.create_course_outline.models.course_outline import CourseOutline
from coursesmith.use_cases.shared.ports.prompts_port import PromptsPort


class CourseOutlineService:
    PROMPT_NAME = "course_outline"

    def __init__(
        self,
        model: str,
        api_key: str,
        prompts_port: PromptsPort,
        prompt_version: int,
    ):
        self._model = model
        self._api_key = api_key
        self._prompt = prompts_port.get_prompt(name=self.PROMPT_NAME, version=prompt_version)

    async def create(self, topic: str) -> CourseOutline:
        prompt = self._prompt.format(topic=topic)
        messages = [{"role": "user", "content": prompt}]
        result = await acompletion(
            messages=messages,
            model=self._model,
            api_key=self._api_key,
            response_format=CourseOutline,
        )
        return CourseOutline.model_validate_json(json_data=result.choices[0].message.content or "")

    async def create_stream(self, topic: str) -> AsyncGenerator[str, None]:
        prompt = self._prompt.format(topic=topic)
        messages = [{"role": "user", "content": prompt}]
        result = await acompletion(
            messages=messages,
            model=self._model,
            api_key=self._api_key,
            stream=True,
        )
        async for chunk in result:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

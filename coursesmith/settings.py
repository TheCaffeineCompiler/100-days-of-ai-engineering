from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LiteLLM Settings
    litellm_model: str
    litellm_api_key: str

    # Course Outline Service Settings
    course_outline_prompt_version: int

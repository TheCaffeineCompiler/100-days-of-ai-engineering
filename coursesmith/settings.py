from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LiteLLM Settings
    litellm_model: str
    litellm_api_key: str
    litellm_retries: int
    litellm_timeout: int

    # Course Outline Service Settings
    course_outline_prompt_version: int

from pydantic_settings import BaseSettings, SettingsConfigDict

from coursesmith.config.logging_config import LogLevel


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Log settings
    log_json_enabled: bool
    log_level: LogLevel

    # LiteLLM Settings
    litellm_model: str
    litellm_api_key: str
    litellm_retries: int
    litellm_timeout: int

    # Course Outline Service Settings
    course_outline_prompt_version: int

    # Tool Settings
    create_title_prompt_version: int
    create_schedule_prompt_version: int
    review_course_prompt_version: int


settings = Settings()

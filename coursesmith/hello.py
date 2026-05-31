import argparse

from dotenv import load_dotenv

from coursesmith import RESOURCES_DIR
from coursesmith.infrastructure.shared.adapters.prompts_adapter import PromptsAdapter
from coursesmith.settings import Settings
from coursesmith.use_cases.create_course_outline.course_outline_service import CourseOutlineService


def main(title: str) -> None:
    load_dotenv()
    settings = Settings()
    prompts_port = PromptsAdapter(base_path=RESOURCES_DIR)
    service = CourseOutlineService(
        model=settings.litellm_model,
        api_key=settings.litellm_api_key,
        prompts_port=prompts_port,
        prompt_version=settings.course_outline_prompt_version,
    )
    print(service.create(title))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("title")
    args = parser.parse_args()
    main(args.title)

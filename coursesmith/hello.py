import argparse
import os

from dotenv import load_dotenv

from coursesmith.use_cases.create_course_outline.course_outline_service import CourseOutlineService


def main(title: str) -> None:
    load_dotenv()
    service = CourseOutlineService(
        model=os.getenv("LITELLM_MODEL", "not-provided"),
        api_key=os.getenv("LITELLM_API_KEY", "not-provided"),
    )
    print(service.create(title))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("title")
    args = parser.parse_args()
    main(args.title)

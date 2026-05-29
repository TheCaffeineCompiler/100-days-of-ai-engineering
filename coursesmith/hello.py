import argparse
import os

from dotenv import load_dotenv
from litellm import completion


def main(prompt: str) -> None:
    load_dotenv()
    messages = [{"role": "user", "content": prompt}]
    response = completion(
        model=os.getenv("LITELLM_MODEL", "not-provided"),
        api_key=os.getenv("LITELLM_API_KEY"),
        messages=messages,
    )
    print(response.choices[0].message.content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    args = parser.parse_args()
    main(args.prompt)

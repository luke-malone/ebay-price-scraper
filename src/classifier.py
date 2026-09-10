import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# Find .env in the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError(
        f"OPENAI_API_KEY is not set. Checked: {ENV_FILE}"
    )

client = OpenAI(api_key=api_key)


def test_gpt() -> None:
    """Test the OpenAI API connection."""
    response = client.responses.create(
        model="gpt-5.6-luna",
        input="Reply with exactly: API connection successful.",
    )

    print(response.output_text)


if __name__ == "__main__":
    test_gpt()
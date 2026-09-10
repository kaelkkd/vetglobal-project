import argparse
import sys

import httpx
from pydantic import ValidationError

from vetglobal.config import Settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Complete a VetGlobal job through the internal API"
    )
    parser.add_argument("job_id", type=int)
    parser.add_argument("--api-url", default="http://localhost:8000")
    result = parser.add_mutually_exclusive_group(required=True)
    result.add_argument("--summary", help="Complete the job successfully with this summary")
    result.add_argument("--error", help="Fail the job with this error")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        settings = Settings()  # type: ignore[call-arg]
        token = settings.internal_service_token.get_secret_value()
    except ValidationError:
        message = "A valid INTERNAL_SERVICE_TOKEN is required in .env or the environment"
        print(message, file=sys.stderr)
        return 2
    if args.job_id <= 0:
        print("job_id must be positive", file=sys.stderr)
        return 2

    if args.summary is not None:
        payload = {"status": "DONE", "summary": args.summary}
    else:
        payload = {"status": "FAILED", "error": args.error}

    try:
        response = httpx.post(
            f"{args.api_url.rstrip('/')}/internal/jobs/{args.job_id}/complete",
            headers={"X-Internal-Token": token},
            json=payload,
            timeout=10.0,
        )
    except httpx.HTTPError as error:
        print(f"Request failed: {error}", file=sys.stderr)
        return 1

    print(response.text)
    return 0 if response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())

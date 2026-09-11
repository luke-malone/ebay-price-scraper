"""Run the eBay scraper locally on a fixed schedule and publish complete runs."""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from google.cloud import storage
import google.auth

BUCKET_NAME = "server-413715-iphone-scraper"
OUTPUT_DIRECTORY = Path("output")
OUTPUT_FILENAMES = (
    "classified.json",
    "python_handled.json",
    "gpt_handled.json",
    "price_eligible.json",
    "price_ineligible.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the scraper locally and upload only complete output sets to GCS."
    )
    parser.add_argument("--interval-minutes", type=float, default=60.0)
    parser.add_argument("--bucket", default=BUCKET_NAME)
    parser.add_argument(
        "--project",
        default=os.getenv("GOOGLE_CLOUD_PROJECT"),
        help="Optional GCP project ID; defaults to GOOGLE_CLOUD_PROJECT when set.",
    )
    parser.add_argument(
        "--once", action="store_true", help="Run one scrape instead of looping."
    )
    return parser.parse_args()


def validate_outputs() -> list[Path]:
    """Ensure the scraper created every required, non-empty JSON output."""
    paths = [OUTPUT_DIRECTORY / filename for filename in OUTPUT_FILENAMES]
    missing = [str(path) for path in paths if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise RuntimeError(f"Required scraper output is missing or empty: {', '.join(missing)}")
    return paths


def upload_outputs(bucket_name: str, paths: list[Path], project: str | None) -> str:
    """Upload one complete local scrape under a single UTC timestamp prefix."""
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    credentials, detected_project = google.auth.default()
    bucket = storage.Client(
        project=project or detected_project or "gcs-data-reader", credentials=credentials
    ).bucket(bucket_name)
    for path in paths:
        destination = f"data/{timestamp}/{path.name}"
        bucket.blob(destination).upload_from_filename(path, content_type="application/json")
        logging.info("Uploaded gs://%s/%s", bucket_name, destination)
    return timestamp


def run_once(bucket_name: str, project: str | None) -> bool:
    """Run the scraper and publish only if it succeeds and creates all outputs."""
    completed = subprocess.run([sys.executable, "main.py"], check=False)
    if completed.returncode != 0:
        logging.error("Scraper failed with exit code %s; nothing was uploaded.", completed.returncode)
        return False
    try:
        paths = validate_outputs()
        timestamp = upload_outputs(bucket_name, paths, project)
    except Exception:
        logging.exception("Output verification or upload failed; run was not fully published.")
        return False
    logging.info("Published complete scrape: %s", timestamp)
    return True


def main() -> int:
    args = parse_args()
    if args.interval_minutes <= 0:
        raise ValueError("--interval-minutes must be greater than zero")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    while True:
        run_once(args.bucket, args.project)
        if args.once:
            return 0
        logging.info("Waiting %s minutes before the next scrape.", args.interval_minutes)
        time.sleep(args.interval_minutes * 60)


if __name__ == "__main__":
    raise SystemExit(main())

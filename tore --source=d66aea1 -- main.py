
import json
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import storage

from src.scraper import scrape_ebay
from src.classifier import classify_listings


# ============================================================
# Configuration
# ============================================================

SEARCH_TERM = "iPhone"
MAX_RESULTS = 100

PROJECT_ID = "project-4127aa68-53ef-44e4-83f"
BUCKET_NAME = "server-413715-iphone-scraper"

SEEN_IDS_BLOB = "seen_item_ids.json"

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


# ============================================================
# Google Cloud Storage
# ============================================================

def get_storage_client():
    return storage.Client(project=PROJECT_ID)


def load_seen_item_ids() -> set[str]:
    client = get_storage_client()

    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(SEEN_IDS_BLOB)

    if not blob.exists():
        print("No previous item-ID history found.")
        return set()

    try:
        data = blob.download_as_text()
        ids = json.loads(data)

        if not isinstance(ids, list):
            return set()

        return {str(item_id) for item_id in ids}

    except Exception as error:
        print(
            f"Could not load seen item IDs: {error}"
        )
        return set()


def save_seen_item_ids(
    item_ids: set[str],
) -> None:

    client = get_storage_client()

    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(SEEN_IDS_BLOB)

    blob.upload_from_string(
        json.dumps(
            sorted(item_ids),
            indent=2,
        ),
        content_type="application/json",
    )


def save_run_to_cloud(
    classified: list[dict],
) -> str:

    client = get_storage_client()

    bucket = client.bucket(BUCKET_NAME)

    timestamp = datetime.now(timezone.utc)

    run_name = (
        f"runs/"
        f"{timestamp.strftime('%Y-%m-%d')}/"
        f"{timestamp.strftime('%H-%M-%S')}.json"
    )

    blob = bucket.blob(run_name)

    blob.upload_from_string(
        json.dumps(
            classified,
            indent=2,
            ensure_ascii=False,
        ),
        content_type="application/json",
    )

    return run_name


# ============================================================
# Local output
# ============================================================

def save_local_json(
    filename: str,
    data: list[dict],
) -> None:

    with (OUTPUT_DIR / filename).open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


# ============================================================
# Main
# ============================================================

print("Starting scraper...")

seen_item_ids = load_seen_item_ids()

print()
print(
    f"Previously seen item IDs: "
    f"{len(seen_item_ids)}"
)


# ------------------------------------------------------------
# Scrape ONLY new listings
# ------------------------------------------------------------

results = scrape_ebay(
    SEARCH_TERM,
    max_results=MAX_RESULTS,
    seen_item_ids=seen_item_ids,
)

print()
print(
    f"Scraping finished. Got "
    f"{len(results)} NEW results."
)


if not results:
    print("No new listings found.")

    raise SystemExit


# ============================================================
# Verify within-run uniqueness
# ============================================================

ids = [
    listing["item_id"]
    for listing in results
    if listing.get("item_id")
]

unique_ids = set(ids)

print()
print("========== ITEM ID CHECK ==========")
print(f"Total listings: {len(ids)}")
print(f"Unique item IDs: {len(unique_ids)}")

if len(ids) == len(unique_ids):
    print("✅ No duplicate item IDs detected.")
else:
    duplicate_count = len(ids) - len(unique_ids)

    print(
        f"❌ {duplicate_count} duplicate "
        f"item ID(s) detected."
    )


# ============================================================
# Classification
# ============================================================

classified = classify_listings(results)


# ============================================================
# Update permanent history
# ============================================================

for listing in results:
    seen_item_ids.add(listing["item_id"])

save_seen_item_ids(seen_item_ids)

print()
print(
    f"Permanent ID history now contains "
    f"{len(seen_item_ids)} IDs."
)


# ============================================================
# Split datasets
# ============================================================

python_handled = [
    listing
    for listing in classified
    if listing["classification_method"] == "python"
]

gpt_handled = [
    listing
    for listing in classified
    if listing["classification_method"] == "gpt"
]

price_eligible = [
    listing
    for listing in classified
    if listing["price_eligible"]
]

price_ineligible = [
    listing
    for listing in classified
    if not listing["price_eligible"]
]


# ============================================================
# Save local outputs
# ============================================================

save_local_json(
    "classified.json",
    classified,
)

save_local_json(
    "python_handled.json",
    python_handled,
)

save_local_json(
    "gpt_handled.json",
    gpt_handled,
)

save_local_json(
    "price_eligible.json",
    price_eligible,
)

save_local_json(
    "price_ineligible.json",
    price_ineligible,
)


# ============================================================
# Save run permanently to Cloud Storage
# ============================================================

run_blob = save_run_to_cloud(
    classified
)


# ============================================================
# Final summary
# ============================================================

print()
print("========== FINISHED ==========")
print(f"New listings processed: {len(classified)}")
print(f"Python handled: {len(python_handled)}")
print(f"GPT handled: {len(gpt_handled)}")
print(f"Price eligible: {len(price_eligible)}")
print(f"Price ineligible: {len(price_ineligible)}")

print()
print("Cloud Storage:")
print(
    f"  gs://{BUCKET_NAME}/{SEEN_IDS_BLOB}"
)
print(
    f"  gs://{BUCKET_NAME}/{run_blob}"
)

print()
print("Local output:")
print("  output/classified.json")
print("  output/python_handled.json")
print("  output/gpt_handled.json")
print("  output/price_eligible.json")
print("  output/price_ineligible.json")


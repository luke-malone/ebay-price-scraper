
import json
from pathlib import Path

from src.scraper import scrape_ebay
from src.classifier import classify_listings


SEARCH_TERM = "iPhone"
MAX_RESULTS = 100

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


print("Starting scraper...")

results = scrape_ebay(
    SEARCH_TERM,
    max_results=MAX_RESULTS,
)

print(
    f"Scraping finished. Got {len(results)} results."
)


# ============================================================
# Check item ID deduplication
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
        f"❌ {duplicate_count} duplicate item ID(s) detected."
    )


if not results:
    raise RuntimeError("No results found; refusing to create or upload an empty dataset.")


# ============================================================
# Classification
# ============================================================

classified = classify_listings(results)


# ============================================================
# Split outputs
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
# Save JSON helper
# ============================================================

def save_json(filename: str, data: list[dict]) -> None:
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
# Save outputs
# ============================================================

save_json("classified.json", classified)
save_json("python_handled.json", python_handled)
save_json("gpt_handled.json", gpt_handled)
save_json("price_eligible.json", price_eligible)
save_json("price_ineligible.json", price_ineligible)


# ============================================================
# Final summary
# ============================================================

print()
print("========== FINISHED ==========")
print(f"Total listings: {len(classified)}")
print(f"Python handled: {len(python_handled)}")
print(f"GPT handled: {len(gpt_handled)}")
print(f"Price eligible: {len(price_eligible)}")
print(f"Price ineligible: {len(price_ineligible)}")

print()
print("Saved:")
print("  output/classified.json")
print("  output/python_handled.json")
print("  output/gpt_handled.json")
print("  output/price_eligible.json")
print("  output/price_ineligible.json")

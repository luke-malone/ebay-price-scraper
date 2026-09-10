import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# ============================================================
# OpenAI setup
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError(
        f"OPENAI_API_KEY is not set. Checked: {ENV_FILE}"
    )

client = OpenAI(api_key=api_key)


# ============================================================
# Obvious exclusions
# ============================================================

OBVIOUS_NON_PHONE_TERMS = [
    "case",
    "cover",
    "screen protector",
    "protector",
    "screen replacement",
    "replacement screen",
    "replacement battery",
    "battery replacement",
    "charger only",
    "cable only",
    "box only",
    "manual only",
    "parts only",
    "for parts",
    "dummy phone",
    "dummy",
    "mock phone",
    "display model",
    "housing",
    "full body",
    "back glass",
]


# ============================================================
# Basic Python extraction
# ============================================================

def extract_price(price_text: str | None) -> float | None:
    """Extract a GBP price from an eBay price string."""

    if not price_text:
        return None

    match = re.search(
        r"£\s*([0-9]+(?:\.[0-9]{1,2})?)",
        price_text.replace(",", ""),
    )

    if not match:
        return None

    return float(match.group(1))


def obvious_non_phone(title: str) -> str | None:
    """Reject listings that are clearly not the actual phone."""

    title_lower = title.lower()

    for term in OBVIOUS_NON_PHONE_TERMS:
        if term in title_lower:
            return f"Obvious non-phone listing: '{term}'"

    return None


def extract_iphone_model(title: str) -> str | None:
    """
    Extract a specific iPhone model.

    Examples:
        iPhone 15
        iPhone 15 Pro
        iPhone 15 Pro Max
        iPhone 15 Plus
        iPhone SE
    """

    pattern = re.compile(
        r"\biphone\s*"
        r"((?:se\s*)?[0-9]{1,2}"
        r"(?:\s*(?:pro\s*max|pro|plus|max))?)\b",
        re.IGNORECASE,
    )

    match = pattern.search(title)

    if not match:
        return None

    model = re.sub(r"\s+", " ", match.group(1).strip())

    model = model.replace("Pro max", "Pro Max")
    model = model.replace("pro max", "Pro Max")

    return f"iPhone {model.title()}"


def extract_storage(title: str) -> int | None:
    """
    Extract storage only when it is explicitly expressed.

    Does NOT treat '128GB RAM' as phone storage.
    """

    title_lower = title.lower()

    # TB first.
    tb_match = re.search(
        r"\b(\d+)\s*tb\b",
        title_lower,
    )

    if tb_match:
        return int(tb_match.group(1)) * 1024

    # Explicit "storage" / "memory".
    explicit_match = re.search(
        r"\b(\d+)\s*gb\s*(?:storage|memory)\b",
        title_lower,
    )

    if explicit_match:
        value = int(explicit_match.group(1))

        if value in {16, 32, 64, 128, 256, 512, 1024}:
            return value

    # Ordinary GB.
    for match in re.finditer(
        r"\b(\d+)\s*gb\b",
        title_lower,
    ):
        value = int(match.group(1))

        after = title_lower[match.end():match.end() + 10]

        # Don't interpret "128GB RAM" as storage.
        if re.match(r"\s*ram\b", after):
            continue

        if value in {16, 32, 64, 128, 256, 512, 1024}:
            return value

    return None


def extract_colour(title: str) -> str | None:
    """Extract a clearly stated iPhone colour."""

    colours = [
        "space black",
        "black titanium",
        "natural titanium",
        "white titanium",
        "blue titanium",
        "desert titanium",
        "deep purple",
        "space grey",
        "space gray",
        "rose gold",
        "midnight",
        "starlight",
        "sierra blue",
        "pacific blue",
        "alpine green",
        "deep blue",
        "purple",
        "blue",
        "green",
        "pink",
        "yellow",
        "red",
        "white",
        "black",
        "gold",
        "coral",
        "silver",
        "graphite",
    ]

    title_lower = title.lower()
    colours.sort(key=len, reverse=True)

    for colour in colours:
        if colour in title_lower:
            return colour.title()

    return None


def extract_battery_health(title: str) -> int | None:
    """Extract an explicit battery-health percentage."""

    patterns = [
        r"\b(\d{2,3})\s*%\s*(?:battery\s*)?(?:health|bh)\b",
        r"\bbattery\s*(?:health)?\s*[:\-]?\s*(\d{2,3})\s*%",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            title,
            re.IGNORECASE,
        )

        if match:
            value = int(match.group(1))

            if 0 <= value <= 100:
                return value

    return None


def title_is_ambiguous(title: str) -> bool:
    """Decide whether the title needs GPT interpretation."""

    title_lower = title.lower()

    if "iphone" not in title_lower:
        return True

    ambiguous_terms = [
        "choose",
        "choice",
        "select",
        "various",
        "multiple models",
        "any model",
    ]

    for term in ambiguous_terms:
        if term in title_lower:
            return True

    # Examples like iPhone 6/7.
    if re.search(r"iphone[^,\n]{0,30}/", title_lower):
        return True

    return False


# ============================================================
# Python classification
# ============================================================

def classify_with_python(listing: dict) -> dict:
    """Extract everything Python can confidently determine."""

    title = listing["title"]

    non_phone_reason = obvious_non_phone(title)

    if non_phone_reason:
        return {
            **listing,
            "price_numeric": extract_price(listing.get("price")),
            "model": None,
            "storage_gb": None,
            "colour": None,
            "battery_health_percent": None,
            "classification_status": "handled",
            "classification_method": "python",
            "reason": non_phone_reason,
            "is_actual_iphone": False,
        }

    model = extract_iphone_model(title)
    storage = extract_storage(title)
    colour = extract_colour(title)
    battery = extract_battery_health(title)

    if not model:
        return {
            **listing,
            "price_numeric": extract_price(listing.get("price")),
            "model": None,
            "storage_gb": storage,
            "colour": colour,
            "battery_health_percent": battery,
            "classification_status": "gpt_required",
            "classification_method": None,
            "reason": "Could not identify iPhone model",
            "is_actual_iphone": None,
        }

    if title_is_ambiguous(title):
        return {
            **listing,
            "price_numeric": extract_price(listing.get("price")),
            "model": model,
            "storage_gb": storage,
            "colour": colour,
            "battery_health_percent": battery,
            "classification_status": "gpt_required",
            "classification_method": None,
            "reason": "Title is ambiguous",
            "is_actual_iphone": None,
        }

    return {
        **listing,
        "price_numeric": extract_price(listing.get("price")),
        "model": model,
        "storage_gb": storage,
        "colour": colour,
        "battery_health_percent": battery,
        "classification_status": "handled",
        "classification_method": "python",
        "reason": None,
        "is_actual_iphone": True,
    }


# ============================================================
# GPT fallback
# ============================================================

def classify_with_gpt(
    listing: dict,
    python_data: dict,
) -> dict:
    """Use GPT for genuinely ambiguous listings."""

    prompt = f"""
You are a structured data classifier for an eBay iPhone
price-analysis system.

LISTING TITLE:
{listing["title"]}

PRICE:
{listing.get("price")}

PYTHON'S INITIAL EXTRACTION:
Model: {python_data.get("model")}
Storage: {python_data.get("storage_gb")}
Colour: {python_data.get("colour")}
Battery health: {python_data.get("battery_health_percent")}

Return ONLY valid JSON matching this exact structure:

{{
  "is_actual_iphone": true,
  "model": "iPhone 15 Pro Max",
  "storage_gb": 256,
  "colour": "Blue Titanium",

  "condition_category": "used",
  "condition_grade": "good",

  "damage": [],
  "battery_health_percent": 89,
  "battery_replaced": false,

  "unlocked": true,
  "network": null,

  "bundle": false,
  "bundle_items": [],

  "confidence": "high",
  "reason": null
}}

RULES:

GENERAL
- Use ONLY information supported by the title.
- Do not invent missing information.
- Use null when something cannot be determined.
- If the listing is clearly not an actual iPhone, set
  is_actual_iphone=false.
- If the title gives multiple possible iPhone models and the exact
  model cannot be determined, set is_actual_iphone=false.

MODEL
- Identify the specific model where possible.
- Distinguish:
  iPhone 15
  iPhone 15 Plus
  iPhone 15 Pro
  iPhone 15 Pro Max
- Do the same for all other generations.
- Treat iPhone SE as its own model.
- Do not confuse model numbers such as A2221 with the model.

STORAGE
- Return storage in GB.
- Valid examples: 16, 32, 64, 128, 256, 512, 1024.
- Do NOT interpret "128GB RAM" as storage.
- Return null if storage is not clearly stated.

COLOUR
- Return the colour when clearly stated.
- Otherwise null.

CONDITION_CATEGORY
Use exactly one:
- "new"
- "used"
- "refurbished"
- "parts_or_repair"
- "unknown"

CONDITION_GRADE
Use exactly one:
- "excellent"
- "very_good"
- "good"
- "fair"
- "poor"
- "unknown"

Examples:
- "Excellent condition" -> excellent
- "Pristine" -> excellent
- "Immaculate" -> excellent
- "Very good" -> very_good
- "Good condition" -> good
- "Poor" -> poor
- Parts/repair -> parts_or_repair

DAMAGE
Return an array containing any clearly stated issues.

Only use:
- "cracked_screen"
- "scratched_screen"
- "cracked_back"
- "scratched_body"
- "camera_issue"
- "face_id_issue"
- "nfc_issue"
- "battery_issue"
- "water_damage"
- "other_damage"

Return [] when none are stated.

BATTERY
- Extract an explicit battery percentage.
- "battery_health_percent" must be an integer or null.
- If a replacement/new battery is explicitly stated, set
  battery_replaced=true.
- Otherwise false or null as appropriate.

UNLOCKED / NETWORK
- Clearly unlocked -> unlocked=true.
- Clearly network locked -> unlocked=false.
- If a network is stated, return it.
- Otherwise use null.

BUNDLE
- bundle=true if meaningful additional products are included.
- Examples: monitor, mouse, powerbank, AirPods.
- A normal phone box or charger does NOT count as a bundle.
- Return meaningful extras in bundle_items.

CONFIDENCE
Use:
- "high"
- "medium"
- "low"

REASON
- null when straightforward.
- Otherwise briefly explain the ambiguity.
"""

    response = client.responses.create(
        model="gpt-5.6-luna",
        input=prompt,
    )

    text = response.output_text.strip()

    try:
        result = json.loads(text)

    except json.JSONDecodeError:
        return {
            **listing,
            "price_numeric": extract_price(listing.get("price")),
            "model": None,
            "storage_gb": None,
            "colour": None,
            "condition_category": "unknown",
            "condition_grade": "unknown",
            "damage": [],
            "battery_health_percent": None,
            "battery_replaced": None,
            "unlocked": None,
            "network": None,
            "bundle": False,
            "bundle_items": [],
            "confidence": "low",
            "classification_status": "gpt_failed",
            "classification_method": "gpt",
            "reason": "GPT returned invalid JSON",
            "is_actual_iphone": None,
        }

    return {
        **listing,
        "price_numeric": extract_price(listing.get("price")),
        "model": result.get("model"),
        "storage_gb": result.get("storage_gb"),
        "colour": result.get("colour"),
        "condition_category": result.get(
            "condition_category",
            "unknown",
        ),
        "condition_grade": result.get(
            "condition_grade",
            "unknown",
        ),
        "damage": result.get("damage", []),
        "battery_health_percent": result.get(
            "battery_health_percent"
        ),
        "battery_replaced": result.get("battery_replaced"),
        "unlocked": result.get("unlocked"),
        "network": result.get("network"),
        "bundle": result.get("bundle", False),
        "bundle_items": result.get("bundle_items", []),
        "confidence": result.get("confidence", "low"),
        "classification_status": "handled",
        "classification_method": "gpt",
        "reason": result.get("reason"),
        "is_actual_iphone": result.get("is_actual_iphone"),
    }


# ============================================================
# Price eligibility
# ============================================================

def determine_price_eligibility(listing: dict) -> dict:
    """
    Mark whether the listing should be included in normal
    market-price calculations.
    """

    if listing.get("is_actual_iphone") is False:
        return {
            **listing,
            "price_eligible": False,
            "price_exclusion_reason": "Not an actual iPhone",
        }

    if listing.get("is_actual_iphone") is None:
        return {
            **listing,
            "price_eligible": False,
            "price_exclusion_reason": (
                "Product could not be confidently identified"
            ),
        }

    if listing.get("condition_category") == "parts_or_repair":
        return {
            **listing,
            "price_eligible": False,
            "price_exclusion_reason": "Parts/repair listing",
        }

    damage = listing.get("damage") or []

    if damage:
        return {
            **listing,
            "price_eligible": False,
            "price_exclusion_reason": (
                f"Damage reported: {', '.join(damage)}"
            ),
        }

    if listing.get("bundle") is True:
        return {
            **listing,
            "price_eligible": False,
            "price_exclusion_reason": (
                "Bundle includes additional products"
            ),
        }

    if listing.get("price_numeric") is None:
        return {
            **listing,
            "price_eligible": False,
            "price_exclusion_reason": "No usable price",
        }

    return {
        **listing,
        "price_eligible": True,
        "price_exclusion_reason": None,
    }


# ============================================================
# Public API
# ============================================================

def classify_listing(listing: dict) -> dict:
    """Python first, GPT only when required."""

    python_result = classify_with_python(listing)

    if python_result["classification_status"] == "handled":
        return python_result

    return classify_with_gpt(
        listing,
        python_result,
    )


def classify_listings(listings: list[dict]) -> list[dict]:
    """Classify all listings and determine price eligibility."""

    classified = []

    python_count = 0
    gpt_count = 0
    eligible_count = 0
    ineligible_count = 0

    for number, listing in enumerate(listings, start=1):

        print(
            f"Classifying {number}/{len(listings)}: "
            f"{listing['title']}"
        )

        result = classify_listing(listing)

        if result["classification_method"] == "python":
            python_count += 1

        elif result["classification_method"] == "gpt":
            gpt_count += 1

        result = determine_price_eligibility(result)

        if result["price_eligible"]:
            eligible_count += 1
        else:
            ineligible_count += 1

        classified.append(result)

    print()
    print("========== CLASSIFICATION ==========")
    print(f"Total listings: {len(classified)}")
    print(f"Handled by Python: {python_count}")
    print(f"Sent to GPT: {gpt_count}")

    print()
    print("========== PRICE ELIGIBILITY ==========")
    print(f"Price eligible: {eligible_count}")
    print(f"Price ineligible: {ineligible_count}")

    return classified
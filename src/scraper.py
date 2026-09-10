
from urllib.parse import quote_plus, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


def get_item_id(url: str) -> str | None:
    """Extract the eBay item ID from a listing URL."""

    try:
        parts = urlparse(url).path.strip("/").split("/")

        if "itm" not in parts:
            return None

        index = parts.index("itm")

        if len(parts) <= index + 1:
            return None

        item_id = parts[index + 1]

        if item_id.isdigit():
            return item_id

    except Exception:
        pass

    return None


def scrape_ebay(
    search_term: str,
    max_results: int = 100,
    seen_item_ids: set[str] | None = None,
) -> list[dict]:
    """
    Scrape eBay UK newest listings.

    The scraper:
    - sorts by newly listed (_sop=10)
    - follows pagination
    - deduplicates within the run
    - skips IDs already seen in previous runs
    - keeps paging until max_results NEW listings are found
    """

    results = []
    seen_this_run = set()

    if seen_item_ids is None:
        seen_item_ids = set()

    with sync_playwright() as p:
        print("Launching browser...")

        browser = p.chromium.launch(
            headless=False
        )

        page = browser.new_page(
            viewport={"width": 1440, "height": 1000},
            locale="en-GB",
            timezone_id="Europe/London",
        )

        page_number = 1

        try:
            while len(results) < max_results:

                search_url = (
                    "https://www.ebay.co.uk/sch/i.html"
                    f"?_nkw={quote_plus(search_term)}"
                    "&_sacat=0"
                    "&_from=R40"
                    "&_sop=10"
                    f"&_pgn={page_number}"
                )

                print()
                print(f"Opening page {page_number}:")
                print(search_url)

                response = page.goto(
                    search_url,
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )

                if response:
                    print(f"HTTP status: {response.status}")

                print(f"Page title: {page.title()}")

                try:
                    page.wait_for_selector(
                        "ul.srp-results > li",
                        timeout=15_000,
                    )
                except PlaywrightTimeoutError:
                    print(
                        f"Timed out waiting for results "
                        f"on page {page_number}."
                    )
                    break

                page.wait_for_timeout(2000)

                items = page.locator(
                    "ul.srp-results > li"
                )

                item_count = items.count()

                print(
                    f"Found {item_count} candidate results "
                    f"on page {page_number}"
                )

                page_added = 0

                for i in range(item_count):

                    if len(results) >= max_results:
                        break

                    item = items.nth(i)

                    try:
                        # --------------------------------------------
                        # URL
                        # --------------------------------------------

                        link_locator = item.locator(
                            "a[href*='/itm/']"
                        )

                        if link_locator.count() == 0:
                            continue

                        url = (
                            link_locator.first
                            .get_attribute("href")
                        )

                        if not url:
                            continue

                        # --------------------------------------------
                        # Item ID
                        # --------------------------------------------

                        item_id = get_item_id(url)

                        if not item_id:
                            continue

                        # Already found on this run.
                        if item_id in seen_this_run:
                            continue

                        # Already processed by an earlier run.
                        if item_id in seen_item_ids:
                            continue

                        # --------------------------------------------
                        # Title
                        # --------------------------------------------

                        title = None

                        image_locator = item.locator(
                            "a[href*='/itm/'] img.s-card__image"
                        )

                        if image_locator.count() > 0:
                            title = (
                                image_locator.first
                                .get_attribute("alt")
                            )

                        if not title:
                            title_locator = item.locator(
                                "a.s-card__link[href*='/itm/']"
                            )

                            if title_locator.count() > 0:
                                title = (
                                    title_locator.first
                                    .inner_text()
                                    .strip()
                                )

                        if title:
                            title = (
                                title
                                .split(" Image ")[0]
                                .strip()
                            )

                        if not title:
                            continue

                        # --------------------------------------------
                        # Price
                        # --------------------------------------------

                        price_locator = item.locator(
                            "span.s-card__price"
                        )

                        if price_locator.count() == 0:
                            price_locator = item.locator(
                                "[class*='price']"
                            )

                        price = (
                            price_locator.first
                            .inner_text()
                            .strip()
                            if price_locator.count() > 0
                            else None
                        )

                        # --------------------------------------------
                        # Add NEW listing
                        # --------------------------------------------

                        results.append(
                            {
                                "item_id": item_id,
                                "title": title,
                                "price": price,
                                "url": url,
                            }
                        )

                        seen_this_run.add(item_id)
                        page_added += 1

                    except Exception as error:
                        print(
                            f"Skipping result {i} on page "
                            f"{page_number}: {error}"
                        )

                print(
                    f"Added {page_added} NEW listings "
                    f"from page {page_number}."
                )

                print(
                    f"New listings collected: "
                    f"{len(results)}/{max_results}"
                )

                # If an entire page contains nothing new, continuing
                # indefinitely is not useful.
                if page_added == 0:
                    print(
                        "No new listings found on this page. "
                        "Stopping pagination."
                    )
                    break

                page_number += 1

        except PlaywrightTimeoutError:
            print("Timed out loading eBay.")

        except Exception as error:
            print(f"Unexpected error: {error}")

        finally:
            browser.close()

    print()
    print(
        f"Finished scraping. Returning "
        f"{len(results)} NEW listings."
    )

    return results


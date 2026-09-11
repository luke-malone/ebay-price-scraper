import os
from urllib.parse import quote_plus, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


EBAY_SEARCH_URL = "https://www.ebay.co.uk/sch/i.html"
NORMAL_CHROMIUM_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class EbayScrapeError(RuntimeError):
    """Raised when eBay does not provide a usable search-results page."""


def build_search_url(search_term: str, page_number: int) -> str:
    """Build and make visible the exact eBay UK search URL being requested."""
    return (
        f"{EBAY_SEARCH_URL}?_nkw={quote_plus(search_term)}&_sacat=0"
        f"&_from=R40&_sop=10&_pgn={page_number}"
    )


def get_item_id(url: str) -> str | None:
    """Extract the eBay item ID from a listing URL."""

    try:
        path_parts = urlparse(url).path.strip("/").split("/")

        if "itm" in path_parts:
            itm_index = path_parts.index("itm")

            if len(path_parts) > itm_index + 1:
                item_id = path_parts[itm_index + 1]

                if item_id.isdigit():
                    return item_id

    except Exception:
        pass

    return None


def scrape_ebay(search_term: str, max_results: int = 100) -> list[dict]:
    """
    Scrape eBay UK search results, newest listings first.

    The scraper:
    - sorts by newly listed
    - follows pagination
    - extracts eBay item IDs
    - removes duplicate listings
    - stops after max_results unique listings
    """

    results = []
    seen_ids = set()

    with sync_playwright() as p:
        print("Launching browser...")

        browser = p.chromium.launch(
            headless=os.getenv("HEADLESS", "false").casefold() == "true"
        )

        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            locale="en-GB",
            timezone_id="Europe/London",
            user_agent=NORMAL_CHROMIUM_USER_AGENT,
            extra_http_headers={"Accept-Language": "en-GB,en;q=0.9"},
        )
        page = context.new_page()
        page.set_default_timeout(15_000)
        print(f"Browser user agent: {NORMAL_CHROMIUM_USER_AGENT}")

        page_number = 1

        try:
            while len(results) < max_results:

                search_url = build_search_url(search_term, page_number)

                print()
                print(f"Opening page {page_number}:")
                print(search_url)

                response = page.goto(
                    search_url,
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )

                status = response.status if response else None
                print(f"HTTP status: {status}")
                print(f"Final URL: {page.url}")
                print(f"Page title: {page.title()}")
                if response is None:
                    raise EbayScrapeError("eBay returned no navigation response")
                if response.status >= 400:
                    raise EbayScrapeError(
                        f"eBay rejected search page {page_number} with HTTP {response.status}"
                    )

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
                    raise EbayScrapeError(
                        f"eBay search results did not load on page {page_number}"
                    )

                page.wait_for_timeout(2000)

                items = page.locator("ul.srp-results > li")
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
                        # ------------------------------------------------
                        # Find listing URL
                        # ------------------------------------------------

                        link_locator = item.locator(
                            "a[href*='/itm/']"
                        )

                        if link_locator.count() == 0:
                            continue

                        url = link_locator.first.get_attribute("href")

                        if not url:
                            continue

                        # ------------------------------------------------
                        # Extract eBay item ID
                        # ------------------------------------------------

                        item_id = get_item_id(url)

                        if not item_id:
                            continue

                        # Skip duplicates.
                        if item_id in seen_ids:
                            continue

                        # ------------------------------------------------
                        # Find title
                        # ------------------------------------------------

                        title = None

                        image_locator = item.locator(
                            "a[href*='/itm/'] img.s-card__image"
                        )

                        if image_locator.count() > 0:
                            title = (
                                image_locator.first
                                .get_attribute("alt")
                            )

                        # Fallback to link text.
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
                            title = title.split(" Image ")[0].strip()

                        if not title:
                            continue

                        # ------------------------------------------------
                        # Find price
                        # ------------------------------------------------

                        price_locator = item.locator(
                            "span.s-card__price"
                        )

                        if price_locator.count() == 0:
                            price_locator = item.locator(
                                "[class*='price']"
                            )

                        price = (
                            price_locator.first.inner_text().strip()
                            if price_locator.count() > 0
                            else None
                        )

                        # ------------------------------------------------
                        # Save listing
                        # ------------------------------------------------

                        results.append(
                            {
                                "item_id": item_id,
                                "title": title,
                                "price": price,
                                "url": url,
                            }
                        )

                        seen_ids.add(item_id)
                        page_added += 1

                    except Exception as error:
                        print(
                            f"Skipping result {i} on page "
                            f"{page_number}: {error}"
                        )

                print(
                    f"Added {page_added} new listings "
                    f"from page {page_number}."
                )

                print(
                    f"Total unique listings: "
                    f"{len(results)}/{max_results}"
                )

                # Prevent infinite pagination if eBay keeps returning
                # pages containing only listings we have already seen.
                if page_added == 0:
                    print(
                        "No new unique listings found. "
                        "Stopping pagination."
                    )
                    break

                page_number += 1

        except PlaywrightTimeoutError as error:
            raise EbayScrapeError("Timed out loading eBay search results") from error

        finally:
            context.close()
            browser.close()

    print()
    print(
        f"Finished scraping. Returning "
        f"{len(results)} unique listings."
    )

    return results

from urllib.parse import quote_plus

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


def scrape_ebay(search_term: str, max_results: int = 10) -> list[dict]:
    """
    Scrape eBay UK search results.

    Args:
        search_term: Product/search term to look for.
        max_results: Maximum number of listings to return.

    Returns:
        A list of dictionaries containing title, price and URL.
    """

    results = []

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

        search_url = (
            "https://www.ebay.co.uk/sch/i.html"
            f"?_nkw={quote_plus(search_term)}"
        )

        print(f"Opening: {search_url}")

        try:
            response = page.goto(
                search_url,
                wait_until="domcontentloaded",
                timeout=30_000,
            )

            if response:
                print(f"HTTP status: {response.status}")

            print(f"Page title: {page.title()}")

            # Wait until the new eBay result cards appear.
            try:
                page.wait_for_selector(
                    "ul.srp-results > li",
                    timeout=15_000,
                )
            except PlaywrightTimeoutError:
                print("Timed out waiting for search results.")
                return results

            # Allow any remaining JavaScript rendering to finish.
            page.wait_for_timeout(2000)

            items = page.locator("ul.srp-results > li")
            item_count = items.count()

            print(f"Found {item_count} candidate results")

            for i in range(min(item_count, max_results)):
                item = items.nth(i)

                try:
                    # The current eBay result cards use s-card__ classes.
                    title_locator = item.locator(
                        "a[href*='/itm/'] img.s-card__image"
                    )

                    if title_locator.count() == 0:
                        # Fallback: find the listing link itself.
                        title_locator = item.locator(
                            "a.s-card__link[href*='/itm/']"
                        )

                    if title_locator.count() == 0:
                        continue

                    # eBay places the full product title in image alt text.
                    image = title_locator.first

                    if awaitable := None:
                        pass

                    title = image.get_attribute("alt")

                    if title:
                        # Remove the trailing image-description text.
                        title = title.split(" Image ")[0].strip()

                    # Find the price.
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

                    # Find the actual listing URL.
                    link_locator = item.locator(
                        "a[href*='/itm/']"
                    )

                    url = (
                        link_locator.first.get_attribute("href")
                        if link_locator.count() > 0
                        else None
                    )

                    # Ignore anything that isn't an actual listing.
                    if not title or not url:
                        continue

                    results.append(
                        {
                            "title": title,
                            "price": price,
                            "url": url,
                        }
                    )

                except Exception as error:
                    print(f"Skipping result {i}: {error}")

            print(f"Successfully extracted {len(results)} listings.")

        except PlaywrightTimeoutError:
            print("Timed out loading eBay.")

        except Exception as error:
            print(f"Unexpected error: {error}")

        finally:
            browser.close()

    return results
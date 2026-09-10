from src.scraper import scrape_ebay


print("Starting scraper...")

results = scrape_ebay("iPhone 15", max_results=10)

print(f"Scraping finished. Got {len(results)} results.")

for listing in results:
    print(listing)
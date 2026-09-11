import unittest

from src.scraper import build_search_url, normal_chromium_user_agent


class SearchUrlTests(unittest.TestCase):
    def test_build_search_url_encodes_search_and_pagination(self) -> None:
        url = build_search_url("iPhone 15 Pro", 3)
        self.assertEqual(
            url,
            "https://www.ebay.co.uk/sch/i.html?_nkw=iPhone+15+Pro&_sacat=0"
            "&_from=R40&_sop=10&_pgn=3",
        )

    def test_user_agent_uses_actual_browser_version(self) -> None:
        self.assertIn("Chrome/123.4.5.6", normal_chromium_user_agent("123.4.5.6"))


if __name__ == "__main__":
    unittest.main()

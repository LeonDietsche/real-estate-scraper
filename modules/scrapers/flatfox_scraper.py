from modules.base_scraper import BaseScraper
from utils.url_builder import build_flatfox_url
from playwright.sync_api import sync_playwright
import os

class FlatfoxScraper(BaseScraper):
    def scrape(self):
        params = self.config["params"]
        url = build_flatfox_url(params)

        with sync_playwright() as p:
            headless = os.environ.get("HEADLESS", "true").lower() == "true"
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()
            print(f"🔍 Navigating to: {url}")
            page.goto(url)

            try:
                page.click('button:has-text("Akzeptieren")', timeout=5000)
            except:
                pass

            page.wait_for_selector(".listing-thumb", timeout=20000)

            listings = []
            for el in page.query_selector_all(".listing-thumb"):
                title = el.query_selector(".listing-thumb-title h2")
                price = el.query_selector(".price")
                link = el.query_selector("a")
                if title and price and link:
                    listings.append({
                        "title": title.inner_text().strip(),
                        "price": price.inner_text().strip() + " CHF",
                        "url": "https://flatfox.ch" + link.get_attribute("href")
                    })

            browser.close()
            return listings
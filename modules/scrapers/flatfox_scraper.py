from modules.base_scraper import BaseScraper
from models.real_estate_listing import RealEstateListing
import re
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
            # print("📄 Dumping HTML preview...")
            # print(page.content()[:1000])

            try:
                page.click('button:has-text("Akzeptieren")', timeout=5000)
            except:
                pass

            page.wait_for_selector(".listing-thumb", timeout=20000)
            page.wait_for_timeout(2000)
            listings = []
            for el in page.query_selector_all(".listing-thumb"):
                title_el = el.query_selector(".listing-thumb-title h2")
                price_el = el.query_selector(".price")
                link_el = el.query_selector("a")
                if title_el and price_el and link_el:
                    title = title_el.inner_text().strip()
                    price = price_el.inner_text().strip()
                    url = "https://flatfox.ch" + link_el.get_attribute("href")

                    rooms_match = re.search(r"([\d.]+)\s*Zimmer", title)
                    rooms = float(rooms_match.group(1)) if rooms_match else None

                    location = title.split(",")[-1].strip() if "," in title else ""
                    listings.append(RealEstateListing(title, price + " CHF", location, url, rooms))

            browser.close()
            return listings
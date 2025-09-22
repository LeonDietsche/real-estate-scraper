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

        headless = os.environ.get("HEADLESS", "true").lower() == "true"
        channel = os.getenv("PW_CHANNEL")  # optional (e.g., "msedge" or "chrome")

        with sync_playwright() as p:
            launch_opts = {"headless": headless}
            if channel:
                launch_opts["channel"] = channel

            browser = p.chromium.launch(**launch_opts)
            page = browser.new_page()
            print(f"🔍 Navigating to: {url}")
            page.goto(url)

            # Accept cookies if visible (best effort)
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

                if not (title_el and price_el and link_el):
                    continue

                title_text = title_el.inner_text().strip()
                price_text = price_el.inner_text().strip()
                href = link_el.get_attribute("href") or ""
                full_url = "https://flatfox.ch" + href

                # Extract rooms from the title if present (e.g., "3.5 Zimmer")
                rooms_match = re.search(r"([\d.]+)\s*Zimmer", title_text)
                rooms_val = float(rooms_match.group(1)) if rooms_match else None

                # Location heuristic: last comma-separated token
                location_text = title_text.split(",")[-1].strip() if "," in title_text else ""

                item = {
                    "title": title_text,
                    "price": price_text,  # keep original (already includes currency on Flatfox)
                    "location": location_text,
                    "url": full_url,
                    "rooms": rooms_val,
                }

                listings.append(RealEstateListing(
                    title=item.get("title"),
                    price=item.get("price"),
                    location=item.get("location"),
                    url=item.get("url"),
                    rooms=item.get("rooms")
                ))

            browser.close()
            return listings

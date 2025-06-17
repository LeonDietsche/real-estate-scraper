from modules.base_scraper import BaseScraper
from utils.url_builder import build_homegate_url
from models.real_estate_listing import RealEstateListing
import re
import subprocess
import json
from playwright.sync_api import sync_playwright

class HomegateScraper(BaseScraper):
    def scrape(self):
        urls = self._get_listing_urls(self.config["params"])
        print(f"🔗 Extracted {len(urls)} listing URLs.")

        raw_results = self._send_urls_to_node(urls)
        listings = []
        for item in raw_results:
            listings.append(RealEstateListing(
                title=item.get("title"),
                price=item.get("price"),
                location=item.get("location"),
                url=item.get("url"),
                rooms=item.get("rooms")
            ))

        return listings

    def _get_listing_urls(self, params):
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(build_homegate_url(params), timeout=30000)

            for script in page.locator("script").all():
                try:
                    content = script.inner_text()
                    if "window.__INITIAL_STATE__" in content:
                        browser.close()
                        return self._extract_listing_urls(content)
                except:
                    continue

            browser.close()
            return []

    def _extract_listing_urls(self, script_text):
        try:
            json_str = script_text.strip().removeprefix("window.__INITIAL_STATE__=")
            data = json.loads(json_str)
            listings = data["resultList"]["search"]["fullSearch"]["result"]["listings"]
            return [f"https://www.homegate.ch/mieten/{l['listing']['id']}" for l in listings if "listing" in l and "id" in l["listing"]]
        except Exception as e:
            print(f"❌ Failed to parse listings: {e}")
            return []

    def _send_urls_to_node(self, urls):
        try:
            proc = subprocess.run(
                ["node", "modules/scrapers/homegate-scraper.js"],
                input=json.dumps(urls),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                check=True
            )
            print("🟡 Raw Node stdout:", proc.stdout)
            print("🔴 Raw Node stderr:", proc.stderr)
            return json.loads(proc.stdout)
        except subprocess.CalledProcessError as e:
            print(f"❌ Node script failed:\n{e.stderr}")
        except json.JSONDecodeError:
            print(f"❌ Failed to parse Node output:\n{proc.stdout}")
        return []

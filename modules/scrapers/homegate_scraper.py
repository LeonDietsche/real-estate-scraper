from modules.base_scraper import BaseScraper
from utils.url_builder import build_homegate_url
from models.real_estate_listing import RealEstateListing
import re
import subprocess
import json
import os
import random
import time
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
                price=item.get("price"),       # now numeric gross (e.g., 3300)
                location=item.get("location"), # "street, postalCode, region"
                url=item.get("url"),
                rooms=item.get("rooms")        # e.g., 4.5
            ))
        return listings

    def _get_listing_urls(self, params):
        # --- Anti-detection tuning ---
        headless = os.environ.get("HEADLESS", "true").lower() == "true"
        channel = os.getenv("PW_CHANNEL")  # e.g., "msedge" or "chrome" to use a real browser build

        # A few realistic desktop Chrome UAs (rotate lightly)
        user_agents = [
            # Windows 10 / Chrome 137 (example)
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            # Windows 11 / Chrome 136
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            # Windows 10 / Chrome 135
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        ]
        ua = random.choice(user_agents)

        # Gentle retry with backoff for transient blocks/challenges
        attempts = 3
        backoff_base = 0.8

        with sync_playwright() as p:
            launch_opts = {"headless": headless}
            if channel:
                launch_opts["channel"] = channel
            browser = p.chromium.launch(**launch_opts)
            try:
                # Make the context look Swiss desktop
                context = browser.new_context(
                    user_agent=ua,
                    locale="de-CH",
                    timezone_id="Europe/Zurich",
                    viewport={"width": 1366, "height": 768},
                    extra_http_headers={
                        "Accept-Language": "de-CH,de;q=0.9,en;q=0.8",
                        "Cache-Control": "no-cache",
                        "Pragma": "no-cache",
                        "Upgrade-Insecure-Requests": "1",
                    },
                )
                # Remove obvious automation fingerprints
                context.add_init_script("""
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['de-CH','de','en']});
Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
// Some sites poke at permissions; return 'prompt' by default
const origQuery = (navigator.permissions && navigator.permissions.query) ? navigator.permissions.query.bind(navigator.permissions) : null;
if (origQuery) {
  navigator.permissions.query = (p) => p && p.name === 'notifications'
    ? Promise.resolve({ state: 'prompt' })
    : origQuery(p);
}
                """)

                page = context.new_page()

                url = build_homegate_url(params)

                for i in range(1, attempts + 1):
                    try:
                        # Small jitter to avoid bursty timing
                        time.sleep(random.uniform(0.3, 0.9))

                        page.goto(url, timeout=30000, wait_until="domcontentloaded")

                        # If there is a cookie banner, try to accept quickly (best effort)
                        try:
                            page.locator("button:has-text('Akzeptieren')").first.click(timeout=2000)
                        except:
                            pass

                        # Optionally wait a moment for scripts to attach
                        time.sleep(random.uniform(0.4, 1.0))

                        # Pull scripts and look for __INITIAL_STATE__
                        for script in page.locator("script").all():
                            try:
                                content = script.inner_text()
                                if "window.__INITIAL_STATE__" in content:
                                    return self._extract_listing_urls(content)
                            except:
                                continue

                        # If not found, treat as soft failure & retry
                        if i < attempts:
                            time.sleep(backoff_base * (2 ** (i - 1)) + random.random() * 0.3)
                            continue
                        else:
                            return []
                    except Exception:
                        if i < attempts:
                            time.sleep(backoff_base * (2 ** (i - 1)) + random.random() * 0.3)
                            continue
                        else:
                            return []
            finally:
                try:
                    browser.close()
                except:
                    pass

    def _extract_listing_urls(self, script_text):
        try:
            json_str = script_text.strip().removeprefix("window.__INITIAL_STATE__=")
            data = json.loads(json_str)
            listings = data["resultList"]["search"]["fullSearch"]["result"]["listings"]
            return [
                f"https://www.homegate.ch/mieten/{l['listing']['id']}"
                for l in listings
                if "listing" in l and "id" in l["listing"]
            ]
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

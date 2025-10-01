from modules.base_scraper import BaseScraper
from utils.url_builder import build_homegate_url
from models.real_estate_listing import RealEstateListing
import re
import subprocess
import json
import os
import random
import time
from typing import List
from playwright.sync_api import sync_playwright, Page


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


# ---- Crawl controls (all configurable via env)
_CRAWL_MIN_DELAY = _env_float("CRAWL_MIN_DELAY_SEC", 2.0)
_CRAWL_JITTER = _env_float("CRAWL_JITTER_SEC", 2.0)
_BACKOFF_MIN = _env_float("CRAWL_BACKOFF_MIN", 10.0)
_BACKOFF_MAX = _env_float("CRAWL_BACKOFF_MAX", 300.0)
_MAX_DETAIL_PER_RUN = _env_int("CRAWL_MAX_DETAIL_PER_RUN", 10)
_NODE_BATCH = _env_int("CRAWL_NODE_BATCH_SIZE", 8)
_NODE_BATCH_PAUSE = _env_float("CRAWL_NODE_BATCH_PAUSE", 4.0)


def _polite_pause():
    # base + jitter
    time.sleep(_CRAWL_MIN_DELAY + random.random() * _CRAWL_JITTER)


def _backoff():
    time.sleep(random.uniform(_BACKOFF_MIN, _BACKOFF_MAX))


def _looks_blocked(page: Page) -> bool:
    """Very lightweight detector for CF/blocks."""
    try:
        t = (page.title() or "").lower()
        u = page.url.lower()
        if "cloudflare" in t or "access denied" in t:
            return True
        if "challenge" in u or "blocked" in u:
            return True
    except Exception:
        pass
    return False


class HomegateScraper(BaseScraper):
    def scrape(self):
        urls = self._get_listing_urls(self.config["params"])
        print(f"🔗 Extracted {len(urls)} listing URLs.")

        # Cap detail pages per run
        if _MAX_DETAIL_PER_RUN > 0 and len(urls) > _MAX_DETAIL_PER_RUN:
            urls = urls[:_MAX_DETAIL_PER_RUN]
            print(f"🔒 Capped detail pages to per-run limit: {_MAX_DETAIL_PER_RUN}")

        # ---- FIX: use a local batch_size instead of mutating _NODE_BATCH
        batch_size = _NODE_BATCH if _NODE_BATCH > 0 else len(urls)

        all_items: List[dict] = []
        for i in range(0, len(urls), batch_size):
            batch = urls[i: i + batch_size]
            items = self._send_urls_to_node(batch)
            all_items.extend(items)
            if i + batch_size < len(urls):
                time.sleep(_NODE_BATCH_PAUSE)  # small pause between batches

        listings = []
        for item in all_items:
            listings.append(RealEstateListing(
                title=item.get("title"),
                price=item.get("price"),
                location=item.get("location"),
                url=item.get("url"),
                rooms=item.get("rooms")
            ))
        return listings


    def _get_listing_urls(self, params):
        # --- Anti-detection tuning ---
        headless = os.environ.get("HEADLESS", "true").lower() == "true"
        channel = os.getenv("PW_CHANNEL")  # e.g., "msedge" or "chrome"

        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        ]
        ua = random.choice(user_agents)

        attempts = 3
        backoff_base = 0.8

        with sync_playwright() as p:
            launch_opts = {"headless": headless}
            if channel:
                launch_opts["channel"] = channel
            browser = p.chromium.launch(**launch_opts)
            try:
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
                context.add_init_script("""
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['de-CH','de','en']});
Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
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
                        _polite_pause()  # <<< pace every navigation
                        page.goto(url, timeout=30000, wait_until="domcontentloaded")

                        # accept cookies (best effort)
                        try:
                            page.locator("button:has-text('Akzeptieren')").first.click(timeout=2000)
                        except:
                            pass

                        time.sleep(random.uniform(0.4, 1.0))

                        # If Cloudflare shows a challenge / access denied, back off hard.
                        if _looks_blocked(page):
                            print("⚠️  Cloudflare/blocked signal on list page, backing off...")
                            _backoff()
                            if i < attempts:
                                continue
                            return []

                        # Look for embedded state
                        for script in page.locator("script").all():
                            try:
                                content = script.inner_text()
                                if "window.__INITIAL_STATE__" in content:
                                    return self._extract_listing_urls(content)
                            except:
                                continue

                        # Soft fail & retry with growing delay
                        if i < attempts:
                            time.sleep(backoff_base * (2 ** (i - 1)) + random.random() * 0.6)
                            continue
                        else:
                            return []
                    except Exception:
                        if i < attempts:
                            time.sleep(backoff_base * (2 ** (i - 1)) + random.random() * 0.6)
                            continue
                        else:
                            return []
            finally:
                try:
                    browser.close()
                except:
                    pass

    def _extract_listing_urls(self, script_text):
        import re
        try:
            # Tolerate spaces & optional semicolon after the assignment
            m = re.search(
                r"window\.__INITIAL_STATE__\s*=\s*(\{.*\})\s*;?",
                script_text.strip(),
                flags=re.DOTALL
            )
            json_str = m.group(1) if m else script_text.strip()

            data = json.loads(json_str)
            listings = (
                data.get("resultList", {})
                    .get("search", {})
                    .get("fullSearch", {})
                    .get("result", {})
                    .get("listings", [])
            )
            return [
                f"https://www.homegate.ch/mieten/{(l.get('listing') or {}).get('id') or l.get('id')}"
                for l in listings
                if ((l.get('listing') or {}).get('id') or l.get('id'))
            ]
        except Exception as e:
            print(f"❌ Failed to parse listings: {e}")
            # Optional: dump a short snippet for debugging
            try:
                with open("debug_homegate_state_snippet.txt", "w", encoding="utf-8") as f:
                    f.write(script_text[:2000])
            except:
                pass
            return []

    def _send_urls_to_node(self, urls: List[str]):
        if not urls:
            return []
        try:
            # Small pacing before heavy work (avoid back-to-back batches)
            _polite_pause()
            proc = subprocess.run(
                ["node", "modules/scrapers/homegate-scraper.js"],
                input=json.dumps(urls),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                check=True
            )
            if proc.stderr.strip():
                print("🔴 Node stderr:", proc.stderr.strip())
            return json.loads(proc.stdout or "[]")
        except subprocess.CalledProcessError as e:
            print(f"❌ Node script failed:\n{e.stderr}")
        except json.JSONDecodeError:
            print(f"❌ Failed to parse Node output:\n{proc.stdout}")
        return []

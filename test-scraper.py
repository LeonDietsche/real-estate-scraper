import subprocess
import json
import re
import sys
from playwright.sync_api import sync_playwright

def build_homegate_url(params, page=1):
    base_url = f"https://www.homegate.ch/mieten/immobilien/plz-{params['zip']}/trefferliste"
    query = []

    if "radius" in params:
        query.append(f"be={params['radius']}")
    if "min_rooms" in params:
        query.append(f"ac={params['min_rooms']}")
    if "max_rooms" in params:
        query.append(f"ad={params['max_rooms']}")
    if "max_price" in params:
        query.append(f"ah={params['max_price']}")

    query.append(f"ep={page}")
    return f"{base_url}?" + "&".join(query)

def extract_listing_urls(script_text):
    try:
        json_str = script_text.strip().removeprefix("window.__INITIAL_STATE__=")
        data = json.loads(json_str)
        listings = data["resultList"]["search"]["fullSearch"]["result"]["listings"]
        return [f"https://www.homegate.ch/mieten/{l['listing']['id']}" for l in listings if "listing" in l and "id" in l["listing"]]
    except Exception as e:
        print(f"❌ Failed to parse listings: {e}")
        return []

def get_listing_urls(params):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(build_homegate_url(params), timeout=30000)

        for script in page.locator("script").all():
            try:
                content = script.inner_text()
                if "window.__INITIAL_STATE__" in content:
                    browser.close()
                    return extract_listing_urls(content)
            except:
                continue

        browser.close()
        return []

def send_urls_to_node(urls):
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


if __name__ == "__main__":
    search_params = {
        "zip": "8001",
        "radius": 2000,
        "min_rooms": 4.5,
        "max_rooms": 4.5,
        "max_price": 3500
    }

    urls = get_listing_urls(search_params)
    print(f"🔗 Extracted {len(urls)} listing URLs.")

    listings = send_urls_to_node(urls)
    for l in listings:
        print(f"🏠 {l['title']}\n🔗 {l['url']}\n")

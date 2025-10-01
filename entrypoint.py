from modules.scrapers.flatfox_scraper import FlatfoxScraper
from modules.scrapers.homegate_scraper import HomegateScraper
from modules.scrapers.vermietungen_stadt_zuerich_scraper import VermietungenStadtZuerichScraper

from dotenv import load_dotenv
load_dotenv()

from utils.whatsapp import send_whatsapp_message
from utils.dedupe_db import init_db, filter_new_listings, mark_seen, save_listings


import os
print("[env] WA_URL=", os.getenv("WHATSAPP_API_URL"))
import time
import sys

from config.search_profiles import search_profiles

selector = os.getenv("PROFILE_SELECTOR", "").strip()
if selector:
    # comma-separated list of profile names to run
    wanted = {name.strip() for name in selector.split(",") if name.strip()}
    before = len(search_profiles)
    search_profiles = [p for p in search_profiles if p["name"] in wanted]
    print(f"[run] limiting to profiles: {sorted(wanted)} (from {before} total)")
    
def print_listings(profile_name, listings):
    print(f"\n✅ New listings for {profile_name}:")
    for listing in listings:
        print(listing)  # uses RealEstateListing.__repr__()

def notify_listings(listings, jid):
    print(f"JID: {jid}")
    delay = float(os.getenv("WHATSAPP_SEND_DELAY_SEC", "10"))

    for l in listings:
        price = l.price or "—"
        location = l.location or "—"
        rooms = l.rooms if l.rooms not in (None, "") else "—"

        message = f"""{l.title}\n
💰 {price}
📍 {location}
🛏️ {rooms} Zimmer
🔗 {l.url}"""

        # quick retry-once wrapper (helps if WA service is momentarily busy)
        try:
            send_whatsapp_message(message, jid=jid)
        except Exception as e:
            # brief backoff then retry once
            time.sleep(min(2 * delay, 3))
            try:
                send_whatsapp_message(message, jid=jid)
            except Exception:
                # last resort: don’t block the rest
                print(f"❌ Failed to send after retry: {l.url} ({e})")

        # pacing so WhatsApp service isn’t flooded
        time.sleep(delay)

def main():
    init_db()  # ensure SQLite is ready

    available_scrapers = {
        "flatfox": FlatfoxScraper,
        "homegate": HomegateScraper,
        "vermietungen-stadt-zuerich": VermietungenStadtZuerichScraper,
    }

    for profile in search_profiles:
        scraper_key = profile["scraper"]
        ScraperClass = available_scrapers.get(scraper_key)

        if not ScraperClass:
            print(f"❌ No scraper found for key: {scraper_key}")
            continue

        scraper = ScraperClass(config=profile)
        listings = scraper.scrape()

        # dedupe by (profile, url)
        print(f'JID entry: {profile["jid"]}')
        new_listings = filter_new_listings(profile["name"], listings)
        if not new_listings:
            print(f"ℹ️ No new listings for {profile['name']}")
            continue

        print_listings(profile["name"], new_listings)
        notify_listings(new_listings, jid=profile["jid"])
        
         # mark after successful handling
         # persist them
        save_listings(profile["name"], new_listings)
        mark_seen(profile["name"], new_listings)

if __name__ == "__main__":
    main()

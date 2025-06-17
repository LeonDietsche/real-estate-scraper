from modules.scrapers.flatfox_scraper import FlatfoxScraper
from modules.scrapers.homegate_scraper import HomegateScraper
from utils.storage import load_seen_urls, save_seen_urls
from utils.whatsapp import send_whatsapp_message

import sys
if "--test" in sys.argv:
    from config.test_search_profiles import search_profiles
else:
    from config.search_profiles import search_profiles

def get_new_listings(listings, seen_urls):
    return [listing for listing in listings if listing.url not in seen_urls]

def print_listings(profile_name, listings):
    print(f"\n✅ New listings for {profile_name}:")
    for listing in listings:
        print(listing)  # uses RealEstateListing.__repr__()

def notify_listings(listings, jid):
    for listing in listings:
        message = f"""{listing.title}
        💰 {listing.price}
        📍 {listing.location}
        🛏️ {listing.rooms} Zimmer
        🔗 {listing.url}"""
        send_whatsapp_message(message, jid=jid)

def main():
    available_scrapers = {
        "flatfox": FlatfoxScraper,
        "homegate": HomegateScraper
    }

    for profile in search_profiles:
        scraper_key = profile["scraper"]
        ScraperClass = available_scrapers.get(scraper_key)

        if not ScraperClass:
            print(f"❌ No scraper found for key: {scraper_key}")
            continue

        scraper = ScraperClass(config=profile)
        listings = scraper.scrape()

        # Uncomment below when you want to resume deduplication + persistence
        # seen = load_seen_urls(profile["name"])
        # new_listings = get_new_listings(listings, seen)
        # if not new_listings:
        #     print(f"ℹ️ No new listings for {profile['name']}")
        #     continue

        print_listings(profile["name"], listings)
        notify_listings(listings, jid=profile["jid"])
        
        #  notify_listings(new_listings, jid=profile["jid"])
        # new_seen = seen.union({l.url for l in new_listings})
        # save_seen_urls(profile["name"], new_seen)

if __name__ == "__main__":
    main()

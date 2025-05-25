from modules.scrapers.flatfox_scraper import FlatfoxScraper
from utils.storage import load_seen_urls, save_seen_urls
from utils.whatsapp import send_whatsapp_message
from config.search_profiles import search_profiles

def get_new_listings(listings, seen_urls):
    """Filter out listings that have already been seen."""
    return [listing for listing in listings if listing["url"] not in seen_urls]

def print_listings(profile_name, listings):
    """Print listings in a readable format."""
    print(f"\n✅ New listings for {profile_name}:")
    for listing in listings:
        print(f"{listing['title']} - {listing['price']}")
        print(f"→ {listing['url']}\n")

def notify_listings(listings, jid):
    """Send new listings via WhatsApp."""
    for listing in listings:
        message = f"""{listing['title']}
💰 {listing['price']}

🔗 {listing['url']}"""
        send_whatsapp_message(message, jid=jid)

def main():
    # Register scraper classes (not instances)
    available_scrapers = {
        "flatfox": FlatfoxScraper,
        # Add future scrapers here: "homegate": HomegateScraper, ...
    }

    for profile in search_profiles:
        scraper_key = profile["scraper"]
        ScraperClass = available_scrapers.get(scraper_key)

        if not ScraperClass:
            print(f"❌ No scraper found for key: {scraper_key}")
            continue

        # Instantiate scraper with profile config
        scraper = ScraperClass(config=profile)
        listings = scraper.scrape()

        # Seen URL logic
        seen = load_seen_urls(profile["name"])
        new_listings = get_new_listings(listings, seen)

        if not new_listings:
            print(f"ℹ️ No new listings for {profile['name']}")
            continue

        print_listings(profile["name"], new_listings)
        notify_listings(new_listings, jid=profile["jid"])

        new_seen = seen.union({listing["url"] for listing in new_listings})
        save_seen_urls(profile["name"], new_seen)

if __name__ == "__main__":
    main()

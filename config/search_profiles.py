import os
from dotenv import load_dotenv

load_dotenv()

search_profiles = [
    {
        "name": "flatfox_zurich_4zimmer",
        "scraper": "flatfox",
        "jid": os.getenv("JID_ZURICH_4ZIMMER"),
        "params": {
            "min_rooms": 4.5,
            "max_price": 3500,
            "bbox": (47.400271, 8.609897, 47.354793, 8.440600),
            "temporary": False,
            "object_categories": ["APARTMENT", "HOUSE"],
            "region": "zuerich",
            "query": "Zürich",
            "take": 48
        }
    }
]

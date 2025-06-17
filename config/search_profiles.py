import os
from dotenv import load_dotenv

load_dotenv()

search_profiles = [
    {
        "name": "homegate_zurich_4zimmer",
        "scraper": "homegate",
        "jid": os.getenv("JID_ZURICH_4ZIMMER"),
        "params": {
            "zip": "8001",
            "radius": 2000,
            "min_rooms": 4.5,
            "max_price": 3500
        }
    }
]

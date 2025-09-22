import os
from dotenv import load_dotenv

load_dotenv()

search_profiles = [
      {
        "name": "flatfox_zurich_4zimmer",
        "scraper": "flatfox",
        "jid": os.getenv("JID_ZURICH_4ZIMMER"),
        "params": {
            "min_rooms": 4,
            "max_price": 3500,
            "bbox": (47.400271, 8.609897, 47.354793, 8.440600),
            "temporary": False,
            "object_categories": ["APARTMENT", "HOUSE"],
            "region": "zuerich",
            "query": "Zürich",
            "take": 48
        }
    },
    {
        "name": "homegate_api_zurich",
        "scraper": "homegate",
        "jid": None,
        "params": {
            "zip": "8001",
            "radius": 2000,
            "min_rooms": 4.5,
            "max_rooms": 4.5,
            "max_price": 3500
        }
    },
    ,
      {
        "name": "homegate_api_sg",
        "scraper": "homegate",
        "jid": os.getenv("JID_SG_1_5ZIMMER"),
        "params": {
            "zip": "9000",
            "radius": 2000,
            "min_rooms": 1.5,
            "max_rooms": 3.5,
            "max_price": 1500
        }
    }
     {
        "name": "vermietungen_stadt_zh_all",
        "scraper": "vermietungen-stadt-zuerich",
        "jid": None,
        "params": {
            "exact_rooms": 4.5
        }
    }
]

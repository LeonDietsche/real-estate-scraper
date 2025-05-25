from urllib.parse import urlencode

def build_flatfox_url(profile):
    base_url = "https://flatfox.ch/de/search/"
    params = {
        "categories": "rent",
        "min_rooms": profile["min_rooms"],
        "max_price": profile["max_price"],
        "is_temporary": str(profile["temporary"]).lower(),
        "ordering": "-insertion",
        "place_name": f"{profile['query']}, Kanton Zürich, Schweiz",
        "place_type": "place",
        "query": profile["query"],
        "regions": profile["region"],
        "take": profile["take"]
    }

    if "bbox" in profile:
        north, east, south, west = profile["bbox"]
        params.update({
            "north": north,
            "east": east,
            "south": south,
            "west": west
        })

    query_string = urlencode(params, doseq=True)
    object_categories = profile["object_categories"]
    category_query = "&" + "&".join([f"object_category={cat}" for cat in object_categories])

    return f"{base_url}?{query_string}{category_query}"

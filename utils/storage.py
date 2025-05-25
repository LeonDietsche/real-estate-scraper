import os
import json

SEEN_DIR = "seen_urls"
os.makedirs(SEEN_DIR, exist_ok=True)

def get_seen_path(profile_name):
    return os.path.join(SEEN_DIR, f"{profile_name}.json")

def load_seen_urls(profile_name):
    path = get_seen_path(profile_name)
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except json.JSONDecodeError:
        print(f"⚠️ Failed to decode seen file for {profile_name}, ignoring it.")
        return set()

def save_seen_urls(profile_name, seen_urls):
    path = get_seen_path(profile_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(list(seen_urls), f, indent=2, ensure_ascii=False)

# utils/dedupe_db.py
import os
import re
import sqlite3
from typing import Iterable, List, Tuple, Optional
from contextlib import contextmanager
from datetime import datetime, timezone

from models.real_estate_listing import RealEstateListing

DEFAULT_DB_PATH = os.environ.get("DEDUP_DB_PATH", "data/dedupe.sqlite3")

def _now_iso() -> str:
    # e.g., "2025-09-12T14:32:05Z"
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

_SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS seen_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_name TEXT NOT NULL,
    url TEXT NOT NULL,
    first_seen_at TEXT NOT NULL, -- ISO-8601 UTC
    last_seen_at  TEXT NOT NULL, -- ISO-8601 UTC
    UNIQUE(profile_name, url)
);

CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_name TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    price_amount REAL,
    price_currency TEXT,
    location TEXT,
    rooms REAL,
    first_seen_at TEXT NOT NULL, -- ISO-8601 UTC
    last_seen_at  TEXT NOT NULL, -- ISO-8601 UTC
    UNIQUE(profile_name, url)
);

CREATE INDEX IF NOT EXISTS idx_listings_profile_lastseen
    ON listings(profile_name, last_seen_at DESC);
"""

@contextmanager
def _conn(db_path: str = DEFAULT_DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        yield con
    finally:
        con.close()

def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    with _conn(db_path) as con:
        con.executescript(_SCHEMA)
        con.commit()

# ------------------------------
# DEDUPE
# ------------------------------

def filter_new_listings(profile_name: str, listings: List[RealEstateListing], db_path: str = DEFAULT_DB_PATH) -> List[RealEstateListing]:
    if not listings:
        return []
    urls = [l.url for l in listings if l.url]
    if not urls:
        return listings
    placeholders = ",".join("?" * len(urls))
    with _conn(db_path) as con:
        cur = con.cursor()
        cur.execute(f"""
            SELECT url FROM seen_listings
            WHERE profile_name = ? AND url IN ({placeholders})
        """, (profile_name, *urls))
        seen = {row[0] for row in cur.fetchall()}
    return [l for l in listings if l.url not in seen]

def mark_seen(profile_name: str, listings: Iterable[RealEstateListing], db_path: str = DEFAULT_DB_PATH) -> None:
    now = _now_iso()
    rows: List[Tuple[str, str, str, str]] = []
    for l in listings:
        if not l.url:
            continue
        rows.append((profile_name, l.url, now, now))
    if not rows:
        return
    with _conn(db_path) as con:
        cur = con.cursor()
        cur.executemany("""
            INSERT INTO seen_listings (profile_name, url, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(profile_name, url)
            DO UPDATE SET last_seen_at=excluded.last_seen_at
        """, rows)
        con.commit()

# ------------------------------
# LISTINGS STORAGE
# ------------------------------

_price_cur_re = re.compile(r"\b([A-Z]{3})\b")
_price_num_re = re.compile(r"([-+]?\d+(?:[.,]\d+)?)")

def _parse_price(price: Optional[str]):
    if not price:
        return (None, None)
    cur = None
    mcur = _price_cur_re.search(price)
    if mcur:
        cur = mcur.group(1)
    cleaned = price.replace("’", "'").replace(" ", "").replace("'", "")
    mnum = _price_num_re.search(cleaned)
    amt = None
    if mnum:
        try:
            amt = float(mnum.group(1).replace(",", "."))
        except Exception:
            amt = None
    return (amt, cur)

def _to_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        return float(str(x).replace(",", "."))
    except Exception:
        return None

def save_listings(profile_name: str, listings: Iterable[RealEstateListing], db_path: str = DEFAULT_DB_PATH) -> None:
    now = _now_iso()
    rows = []
    for l in listings:
        if not l.url:
            continue
        amount, currency = _parse_price(l.price if isinstance(l.price, str) else str(l.price) if l.price is not None else "")
        rooms_val = _to_float(l.rooms)
        rows.append((
            profile_name,
            l.url,
            l.title or "",
            amount,
            currency,
            l.location or "",
            rooms_val,
            now,
            now
        ))
    if not rows:
        return
    with _conn(db_path) as con:
        cur = con.cursor()
        cur.executemany("""
            INSERT INTO listings (
                profile_name, url, title, price_amount, price_currency,
                location, rooms, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(profile_name, url) DO UPDATE SET
                title=excluded.title,
                price_amount=excluded.price_amount,
                price_currency=excluded.price_currency,
                location=excluded.location,
                rooms=excluded.rooms,
                last_seen_at=excluded.last_seen_at
        """, rows)
        con.commit()

def get_recent_listings(profile_name: str, limit: int = 50, db_path: str = DEFAULT_DB_PATH) -> List[dict]:
    with _conn(db_path) as con:
        cur = con.cursor()
        cur.execute("""
            SELECT url, title, price_amount, price_currency, location, rooms, first_seen_at, last_seen_at
            FROM listings
            WHERE profile_name = ?
            ORDER BY last_seen_at DESC
            LIMIT ?
        """, (profile_name, limit))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

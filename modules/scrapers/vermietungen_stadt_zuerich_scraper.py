from __future__ import annotations
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from modules.base_scraper import BaseScraper
from models.real_estate_listing import RealEstateListing
from utils.url_builder import build_stadt_zuerich_url

def _first_num(txt: str) -> str:
    if not txt:
        return ""
    m = re.search(r"\d+(?:[.,]\d+)?", txt.replace("’", "'"))
    return m.group(0).replace(",", ".") if m else ""

class VermietungenStadtZuerichScraper(BaseScraper):
    def __init__(self, config: dict):
        super().__init__(config)
        self._s = requests.Session()
        self._s.headers.update({
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124.0 Safari/537.36"),
            "Accept": "text/html,application/xhtml+xml",
        })

    def _list_url(self) -> str:
        # Keep signature parity with other builders; params are ignored for now
        return build_stadt_zuerich_url(self.config.get("params"))

    def _post_with_filters(self, min_rooms: float | None, max_rooms: float | None) -> str:
        list_url = self._list_url()

        r0 = self._s.get(list_url, timeout=20)
        r0.raise_for_status()
        csrf = self._s.cookies.get("csrftoken")

        headers = {
            "Referer": list_url,
            "Origin": "https://www.vermietungen.stadt-zuerich.ch",
            "X-Requested-With": "XMLHttpRequest",
        }
        if csrf:
            headers["X-CSRFToken"] = csrf

        if min_rooms is not None and max_rooms is not None:
            rooms_value = f"{min_rooms},{max_rooms}"
        elif min_rooms is not None:
            rooms_value = f"{min_rooms},{min_rooms}"
        elif max_rooms is not None:
            rooms_value = f"{max_rooms},{max_rooms}"
        else:
            rooms_value = ""

        data = {"rooms": rooms_value, "search": ""}

        r1 = self._s.post(list_url, headers=headers, data=data, timeout=20)
        if r1.ok and "text/html" in r1.headers.get("content-type", "") and r1.text.strip():
            return r1.text
        return r0.text

    def scrape(self) -> list[RealEstateListing]:
        params = self.config.get("params", {}) or {}

        def _to_float(x):
            try:
                return float(x) if x is not None else None
            except Exception:
                return None

        exact_rooms = _to_float(params.get("exact_rooms"))
        min_rooms = _to_float(params.get("min_rooms"))
        max_rooms = _to_float(params.get("max_rooms"))

        if exact_rooms is not None:
            html = self._post_with_filters(exact_rooms, exact_rooms)
        elif min_rooms is not None or max_rooms is not None:
            html = self._post_with_filters(min_rooms, max_rooms)
        else:
            r = self._s.get(self._list_url(), timeout=20)
            r.raise_for_status()
            html = r.text

        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("div.table-container.main-table table tbody tr")

        listings: list[RealEstateListing] = []
        for tr in rows:
            address = (tr.select_one("td.publicated_adress") or {}).get_text(strip=True)
            rooms_txt = (tr.select_one("td.rooms") or {}).get_text(strip=True)
            brutto_txt = (tr.select_one("td.rentalgross") or {}).get_text(strip=True)

            apply_a = tr.select_one("td.apply_button a.apply_button")
            href = apply_a.get("href") if apply_a else ""
            url = urljoin("https://www.vermietungen.stadt-zuerich.ch", href) if href else self._list_url()

            price_str = _first_num(brutto_txt)
            rooms_str = _first_num(rooms_txt)

            # client-side safety net
            def _f(x):
                try: return float(x)
                except Exception: return None
            rv = _f(rooms_str)

            if exact_rooms is not None and (rv is None or abs(rv - exact_rooms) > 1e-9):
                continue
            if min_rooms is not None and (rv is None or rv < min_rooms):
                continue
            if max_rooms is not None and (rv is None or rv > max_rooms):
                continue

            parts = []
            if address: parts.append(address)
            if rooms_str: parts.append(f"{rooms_str} Zi.")
            if price_str: parts.append(f"CHF {price_str}")
            title = ", ".join(parts) + " | vermietungen.stadt-zuerich.ch"

            listings.append(
                RealEstateListing(
                    title=title,
                    price=(f"CHF {price_str}" if price_str else ""),
                    location="Zürich",
                    url=url,
                    rooms=(rooms_str or ""),
                )
            )

        return listings

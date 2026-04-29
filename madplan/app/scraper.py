import requests
from bs4 import BeautifulSoup

_TIMEOUT = 10
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "da-DK,da;q=0.9",
    "Accept": "application/json, text/html, */*",
}

# Approximate coordinates for Danish postal code areas (first digit)
_POSTAL_COORDS = {
    "1": (55.6761, 12.5683),  # Copenhagen
    "2": (55.7, 12.5),
    "3": (55.9, 12.3),        # North Zealand
    "4": (55.4, 11.7),        # Zealand
    "5": (55.4, 10.4),        # Funen / Odense
    "6": (55.2,  9.5),        # South Jutland
    "7": (56.2,  9.5),        # Mid Jutland
    "8": (56.1563, 10.2108),  # Aarhus
    "9": (57.0488,  9.9187),  # North Jutland / Aalborg
}

# Store brand name fragments → internal store key
_BRAND_MAP = {
    "lidl":      "lidl",
    "rema 1000": "rema",
    "rema1000":  "rema",
    "løvbjerg":  "loevbjerg",
    "lovbjerg":  "loevbjerg",
}


def _postal_to_coords(postal_code: str) -> tuple:
    if postal_code:
        return _POSTAL_COORDS.get(postal_code[0], (56.0, 10.0))
    return (56.0, 10.0)  # geographic centre of Denmark


def fetch_all_store_offers(postal_code: str = "") -> dict:
    """Fetch weekly offers for Lidl, Rema 1000 and Løvbjerg using the
    eTilbudsavis public search API, which covers all three stores in one call.

    Falls back to direct site scraping if the API is unavailable.

    Returns: {"lidl": [...], "rema": [...], "loevbjerg": [...]}
    """
    result = _fetch_etilbudsavis(postal_code)

    if not any(result.values()):
        print("eTilbudsavis returned nothing — trying fallback scrapers", flush=True)
        lidl = _scrape_lidl()
        rema = _scrape_rema()
        loev = _scrape_loevbjerg()
        result = {"lidl": lidl, "rema": rema, "loevbjerg": loev}

    return result


# ── eTilbudsavis ──────────────────────────────────────────────────────────── #

def _fetch_etilbudsavis(postal_code: str) -> dict:
    lat, lng = _postal_to_coords(postal_code)
    result: dict = {"lidl": [], "rema": [], "loevbjerg": []}
    try:
        r = requests.get(
            "https://api.etilbudsavis.dk/v2/offers/search",
            params={
                "r_lat": lat,
                "r_lng": lng,
                "r_radius": 50000,   # 50 km — covers most of Denmark
                "r_locale": "da_DK",
                "limit": 500,
                "offset": 0,
            },
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        print(f"eTilbudsavis status: {r.status_code}", flush=True)
        r.raise_for_status()
        offers = r.json()
        if not isinstance(offers, list):
            print(f"eTilbudsavis unexpected response type: {type(offers)}", flush=True)
            return result

        for item in offers:
            heading = item.get("heading", "").strip()
            if not heading:
                continue
            brand_raw = (item.get("branding") or {}).get("name", "").lower()
            for pattern, key in _BRAND_MAP.items():
                if pattern in brand_raw:
                    result[key].append(heading)
                    break

        total = sum(len(v) for v in result.values())
        print(
            f"eTilbudsavis: {total} offers — "
            + ", ".join(f"{k}={len(v)}" for k, v in result.items()),
            flush=True,
        )
    except Exception as e:
        print(f"eTilbudsavis error: {e}", flush=True)

    return result


# ── Fallback HTML scrapers ────────────────────────────────────────────────── #

def _scrape_lidl() -> list:
    for url in [
        "https://www.lidl.dk/c/tilbudsavis/s10013730",
        "https://www.lidl.dk/c/ugens-tilbud/a10014935",
    ]:
        try:
            r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            products = []
            for sel in [
                ".product-grid-box__title",
                ".offer-item__title",
                "[class*='productName']",
                "[class*='product-name']",
                ".nuc-a-product-tile__title",
            ]:
                found = [el.get_text(strip=True) for el in soup.select(sel)]
                if found:
                    products.extend(found)
            if products:
                deduped = list(dict.fromkeys(p for p in products if p))
                print(f"Lidl HTML scrape: {len(deduped)} items", flush=True)
                return deduped
        except Exception as e:
            print(f"Lidl scrape error ({url}): {e}", flush=True)
    return []


def _scrape_rema() -> list:
    for url in [
        "https://www.rema1000.dk/tilbud",
        "https://etilbudsavis.dk/Rema-1000",
    ]:
        try:
            r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            products = []
            for sel in [
                "[class*='product-name']",
                "[class*='productName']",
                "[class*='offer-title']",
                ".product-card__name",
            ]:
                found = [el.get_text(strip=True) for el in soup.select(sel)]
                if found:
                    products.extend(found)
            if products:
                deduped = list(dict.fromkeys(p for p in products if p))
                print(f"Rema HTML scrape: {len(deduped)} items", flush=True)
                return deduped
        except Exception as e:
            print(f"Rema scrape error ({url}): {e}", flush=True)
    return []


def _scrape_loevbjerg() -> list:
    for url in [
        "https://www.lovbjerg.dk/avis",
        "https://etilbudsavis.dk/Lovbjerg",
    ]:
        try:
            r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            products = []
            for sel in [
                ".product-title",
                ".offer-title",
                "[class*='productTitle']",
                "[class*='offer-name']",
            ]:
                found = [el.get_text(strip=True) for el in soup.select(sel)]
                if found:
                    products.extend(found)
            if products:
                deduped = list(dict.fromkeys(p for p in products if p))
                print(f"Løvbjerg HTML scrape: {len(deduped)} items", flush=True)
                return deduped
        except Exception as e:
            print(f"Løvbjerg scrape error ({url}): {e}", flush=True)
    return []

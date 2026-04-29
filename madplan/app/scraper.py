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
}


def fetch_lidl_offers() -> list:
    """Scrape current weekly offers from lidl.dk.

    Returns a list of product name strings.
    Falls back to [] on any error.
    """
    urls = [
        "https://www.lidl.dk/c/tilbudsavis/s10013730",
        "https://www.lidl.dk/c/ugens-tilbud/a10014935",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            products = []
            # Lidl product cards use various selectors — try the most common ones
            for sel in [
                ".product-grid-box__title",
                ".offer-item__title",
                "[class*='productName']",
                "[class*='product-name']",
                "h3.product-grid-box__desc-title",
                ".nuc-a-product-tile__title",
            ]:
                found = [el.get_text(strip=True) for el in soup.select(sel) if el.get_text(strip=True)]
                if found:
                    products.extend(found)
            if products:
                print(f"Lidl scrape: {len(products)} offers from {url}", flush=True)
                return list(dict.fromkeys(products))  # deduplicate, preserve order
        except Exception as e:
            print(f"Lidl scrape error ({url}): {e}", flush=True)
    return []


def fetch_loevbjerg_offers() -> list:
    """Scrape current offers from Løvbjerg.

    Tries lovbjerg.dk/avis first, then etilbudsavis.dk/Lovbjerg as fallback.
    Returns a list of product name strings.
    Falls back to [] on any error.
    """
    attempts = [
        ("https://www.lovbjerg.dk/avis", _parse_loevbjerg_direct),
        ("https://etilbudsavis.dk/Lovbjerg", _parse_etilbudsavis),
    ]
    for url, parser in attempts:
        try:
            r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            r.raise_for_status()
            products = parser(r.text)
            if products:
                print(f"Løvbjerg scrape: {len(products)} offers from {url}", flush=True)
                return products
        except Exception as e:
            print(f"Løvbjerg scrape error ({url}): {e}", flush=True)
    return []


def _parse_loevbjerg_direct(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    products = []
    for sel in [
        ".product-title",
        ".offer-title",
        "[class*='productTitle']",
        "[class*='offer-name']",
        "h3", "h4",
    ]:
        found = [el.get_text(strip=True) for el in soup.select(sel) if el.get_text(strip=True)]
        if found:
            products.extend(found)
    return list(dict.fromkeys(products))


def _parse_etilbudsavis(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    products = []
    for sel in [
        "[class*='offer']",
        "[class*='product']",
        ".catalog-offer",
        ".catalog-product",
    ]:
        found = [el.get_text(strip=True) for el in soup.select(sel) if el.get_text(strip=True)]
        if found:
            products.extend(found[:50])  # limit to avoid noise
    return list(dict.fromkeys(products))

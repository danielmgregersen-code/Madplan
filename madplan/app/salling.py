import requests

_BASE = "https://api.sallinggroup.com/v1"
_TIMEOUT = 10


def _headers(api_key: str) -> dict:
    # Salling Group uses Ocp-Apim-Subscription-Key, not Bearer
    return {"Ocp-Apim-Subscription-Key": api_key}


def _brand_from_store_name(name: str) -> str:
    n = name.lower()
    if "føtex" in n or "foetex" in n:
        return "foetex"
    if "netto" in n:
        return "netto"
    if "bilka" in n or "salling" in n:
        return "foetex"  # group Bilka/Salling with Føtex
    return ""


def fetch_food_waste_offers(api_key: str, postal_code: str) -> list:
    """Fetch near-expiry discounted items from all Salling stores near postal_code.

    Uses GET /v1/food-waste/?zip={postal_code} which returns clearances for
    all Salling-brand stores in the area in one call.
    Returns: [{"store": "foetex"|"netto", "product": str, "price": str}]
    """
    try:
        r = requests.get(
            f"{_BASE}/food-waste/",
            params={"zip": postal_code},
            headers=_headers(api_key),
            timeout=_TIMEOUT,
        )
        print(f"Salling food-waste status: {r.status_code} (zip={postal_code})", flush=True)
        r.raise_for_status()
        data = r.json()

        # Response may be a list of clearance objects directly, or {"clearances": [...]}
        if isinstance(data, dict):
            items = data.get("clearances", [])
        elif isinstance(data, list):
            items = data
        else:
            items = []

        offers = []
        for item in items:
            if not isinstance(item, dict):
                continue
            store_name = item.get("store_name", "")
            brand = _brand_from_store_name(store_name)
            if not brand:
                continue
            product = (
                item.get("product_description")
                or item.get("description")
                or item.get("heading")
                or ""
            )
            price = item.get("offer_new_price", item.get("newPrice", ""))
            if not product:
                continue
            price_str = f"{price:.2f} kr".replace(".", ",") if isinstance(price, (int, float)) else str(price)
            offers.append({"store": brand, "product": product, "price": price_str})

        print(f"Salling: {len(offers)} food-waste offers ({postal_code})", flush=True)
        return offers

    except Exception as e:
        print(f"Salling food-waste error: {e}", flush=True)
        return []

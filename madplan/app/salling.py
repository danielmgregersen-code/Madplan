import requests

_BASE = "https://api.sallinggroup.com/v1"
_TIMEOUT = 10
_BRAND_MAP = {"foetex": "foetex", "netto": "netto"}


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"}


def find_store_ids(api_key: str, postal_code: str) -> dict:
    """Return {brand: [store_id, ...]} for Føtex and Netto stores near postal_code."""
    try:
        r = requests.get(
            f"{_BASE}/stores",
            params={"zip": postal_code, "per_page": 20},
            headers=_headers(api_key),
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        stores = r.json()
        result: dict = {"foetex": [], "netto": []}
        for store in stores:
            brand = store.get("brand", "").lower()
            sid = store.get("id")
            if brand in result and sid:
                result[brand].append(sid)
        return result
    except Exception as e:
        print(f"Salling find_store_ids error: {e}", flush=True)
        return {}


def fetch_food_waste_offers(api_key: str, store_ids: dict) -> list:
    """Fetch discounted near-expiry products from Føtex + Netto stores.

    Returns a flat list of dicts: {store, product, price}.
    """
    offers = []
    for brand, ids in store_ids.items():
        for sid in ids[:3]:  # limit to 3 stores per brand
            try:
                r = requests.get(
                    f"{_BASE}/food-waste/{sid}",
                    headers=_headers(api_key),
                    timeout=_TIMEOUT,
                )
                r.raise_for_status()
                data = r.json()
                clearances = data.get("clearances", [])
                for item in clearances:
                    offer = item.get("offer", {})
                    product = offer.get("description", "")
                    price = offer.get("newPrice", "")
                    if product:
                        offers.append({
                            "store": brand,
                            "product": product,
                            "price": f"{price} kr" if price else "",
                        })
            except Exception as e:
                print(f"Salling food-waste error ({brand}/{sid}): {e}", flush=True)
    return offers

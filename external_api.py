import requests

BASE_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
BASE_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"

REQUEST_TIMEOUT = 10

# OpenFoodFacts returns 403 without a descriptive User-Agent.
HEADERS = {
    "User-Agent": "InventoryManagementSystem/1.0 (student lab project; contact: dev@example.com)"
}


class ExternalAPIError(Exception):
    pass


def _normalize(product: dict) -> dict:
    return {
        "name": product.get("product_name") or product.get("generic_name") or "Unknown product",
        "barcode": product.get("code"),
        "category": (product.get("categories") or "").split(",")[0].strip() or None,
        "description": product.get("generic_name") or product.get("ingredients_text") or "",
        "image_url": product.get("image_url") or product.get("image_front_url"),
        # OpenFoodFacts has no price/stock concept, default to 0 and let
        # the user fill these in after import.
        "price": 0.0,
        "quantity": 0,
        "source": "openfoodfacts",
    }


def fetch_by_barcode(barcode: str) -> dict:
    try:
        resp = requests.get(
            BASE_PRODUCT_URL.format(barcode=barcode),
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ExternalAPIError(f"Failed to reach OpenFoodFacts: {exc}") from exc

    payload = resp.json()
    if payload.get("status") != 1 or "product" not in payload:
        return None
    return _normalize(payload["product"])


def search_by_name(name: str, page_size: int = 10) -> list:
    params = {
        "search_terms": name,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": page_size,
    }
    try:
        resp = requests.get(BASE_SEARCH_URL, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ExternalAPIError(f"Failed to reach OpenFoodFacts: {exc}") from exc

    payload = resp.json()
    products = payload.get("products", [])
    return [_normalize(p) for p in products]

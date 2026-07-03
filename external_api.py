"""
external_api.py
----------------
Thin wrapper around the OpenFoodFacts public API.

Docs: https://world.openfoodfacts.org/data

We expose two lookups:
    * fetch_by_barcode(barcode) -> single product dict (or None)
    * search_by_name(name, page_size) -> list of product dicts

Both return data already normalized into the shape our `items` table
expects (name, barcode, category, description, image_url, price, quantity),
so the Flask layer can pass the result straight into database.create_item().
"""
import requests

BASE_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
BASE_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"

REQUEST_TIMEOUT = 10  # seconds


class ExternalAPIError(Exception):
    """Raised when the OpenFoodFacts API is unreachable or returns bad data."""


def _normalize(product: dict) -> dict:
    """Map an OpenFoodFacts 'product' payload to our internal item schema."""
    return {
        "name": product.get("product_name") or product.get("generic_name") or "Unknown product",
        "barcode": product.get("code"),
        "category": (product.get("categories") or "").split(",")[0].strip() or None,
        "description": product.get("generic_name") or product.get("ingredients_text") or "",
        "image_url": product.get("image_url") or product.get("image_front_url"),
        # OpenFoodFacts has no price/quantity-in-stock concept, so these
        # default to sane placeholders the user can edit after import.
        "price": 0.0,
        "quantity": 0,
        "source": "openfoodfacts",
    }


def fetch_by_barcode(barcode: str) -> dict:
    """Look up a single product by its barcode. Returns None if not found."""
    try:
        resp = requests.get(BASE_PRODUCT_URL.format(barcode=barcode), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ExternalAPIError(f"Failed to reach OpenFoodFacts: {exc}") from exc

    payload = resp.json()
    if payload.get("status") != 1 or "product" not in payload:
        return None
    return _normalize(payload["product"])


def search_by_name(name: str, page_size: int = 10) -> list:
    """Search OpenFoodFacts by free-text product name."""
    params = {
        "search_terms": name,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": page_size,
    }
    try:
        resp = requests.get(BASE_SEARCH_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ExternalAPIError(f"Failed to reach OpenFoodFacts: {exc}") from exc

    payload = resp.json()
    products = payload.get("products", [])
    return [_normalize(p) for p in products]

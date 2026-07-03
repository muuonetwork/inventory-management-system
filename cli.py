"""
cli.py
------
Simple command-line interface for the Inventory Management System.

This talks to the Flask API over HTTP (so it exercises the same code
path a real front-end would), rather than importing the database
module directly. Run the API first:

    python app.py

then, in another terminal:

    python cli.py
"""
import os
import sys

import requests

API_BASE = os.environ.get("INVENTORY_API_BASE", "http://127.0.0.1:5000/api")


def _print_item(item: dict) -> None:
    print(
        f"  [{item['id']}] {item['name']}  "
        f"qty={item['quantity']}  price=${item['price']:.2f}  "
        f"category={item.get('category') or '-'}  barcode={item.get('barcode') or '-'}"
    )


def list_items():
    resp = requests.get(f"{API_BASE}/items")
    if resp.status_code != 200:
        print("Error fetching items:", resp.text)
        return
    items = resp.json()
    if not items:
        print("No items in inventory yet.")
        return
    print(f"\n{len(items)} item(s):")
    for item in items:
        _print_item(item)


def view_item():
    item_id = input("Item ID: ").strip()
    resp = requests.get(f"{API_BASE}/items/{item_id}")
    if resp.status_code == 404:
        print("Item not found.")
        return
    if resp.status_code != 200:
        print("Error:", resp.text)
        return
    item = resp.json()
    for key, value in item.items():
        print(f"  {key}: {value}")


def add_item():
    name = input("Name: ").strip()
    category = input("Category (optional): ").strip() or None
    barcode = input("Barcode (optional): ").strip() or None
    try:
        quantity = int(input("Quantity [0]: ").strip() or 0)
        price = float(input("Price [0.00]: ").strip() or 0.0)
    except ValueError:
        print("Quantity/price must be numeric.")
        return

    payload = {
        "name": name,
        "category": category,
        "barcode": barcode,
        "quantity": quantity,
        "price": price,
    }
    resp = requests.post(f"{API_BASE}/items", json=payload)
    if resp.status_code == 201:
        print("Created:")
        _print_item(resp.json())
    else:
        print("Error creating item:", resp.text)


def update_item():
    item_id = input("Item ID to update: ").strip()
    print("Leave a field blank to keep it unchanged.")
    updates = {}
    name = input("New name: ").strip()
    if name:
        updates["name"] = name
    category = input("New category: ").strip()
    if category:
        updates["category"] = category
    quantity = input("New quantity: ").strip()
    if quantity:
        updates["quantity"] = int(quantity)
    price = input("New price: ").strip()
    if price:
        updates["price"] = float(price)

    if not updates:
        print("Nothing to update.")
        return

    resp = requests.patch(f"{API_BASE}/items/{item_id}", json=updates)
    if resp.status_code == 200:
        print("Updated:")
        _print_item(resp.json())
    else:
        print("Error updating item:", resp.text)


def delete_item():
    item_id = input("Item ID to delete: ").strip()
    confirm = input(f"Are you sure you want to delete item {item_id}? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return
    resp = requests.delete(f"{API_BASE}/items/{item_id}")
    if resp.status_code == 200:
        print("Deleted.")
    else:
        print("Error deleting item:", resp.text)


def search_external():
    choice = input("Search by (b)arcode or (n)ame? ").strip().lower()
    if choice == "b":
        barcode = input("Barcode: ").strip()
        resp = requests.get(f"{API_BASE}/external/barcode/{barcode}")
        if resp.status_code != 200:
            print("Error:", resp.text)
            return
        product = resp.json()
        print("\nFound product:")
        for key, value in product.items():
            print(f"  {key}: {value}")
    else:
        name = input("Product name: ").strip()
        resp = requests.get(f"{API_BASE}/external/search", params={"name": name})
        if resp.status_code != 200:
            print("Error:", resp.text)
            return
        results = resp.json()
        if not results:
            print("No results found.")
            return
        print(f"\n{len(results)} result(s):")
        for i, product in enumerate(results):
            print(f"  [{i}] {product['name']}  (barcode={product.get('barcode')})")


def import_from_external():
    choice = input("Import by (b)arcode or (n)ame search? ").strip().lower()
    payload = {}
    if choice == "b":
        payload["barcode"] = input("Barcode: ").strip()
    else:
        payload["name"] = input("Product name to search: ").strip()
        payload["index"] = input("Result index to import [0]: ").strip() or 0

    price = input("Set a price for this item [0.00]: ").strip()
    quantity = input("Set a starting quantity [0]: ").strip()
    if price:
        payload["price"] = float(price)
    if quantity:
        payload["quantity"] = int(quantity)

    resp = requests.post(f"{API_BASE}/items/import", json=payload)
    if resp.status_code == 201:
        print("Imported into inventory:")
        _print_item(resp.json())
    else:
        print("Error importing item:", resp.text)


MENU = """
==== Inventory Management CLI ====
1) List all items
2) View item by ID
3) Add item manually
4) Update item
5) Delete item
6) Search external product database (OpenFoodFacts)
7) Import external product into inventory
0) Exit
"""

ACTIONS = {
    "1": list_items,
    "2": view_item,
    "3": add_item,
    "4": update_item,
    "5": delete_item,
    "6": search_external,
    "7": import_from_external,
}


def main():
    print(f"Connecting to API at {API_BASE}")
    try:
        requests.get(f"{API_BASE}/health", timeout=3)
    except requests.RequestException:
        print("Warning: could not reach the API. Is 'python app.py' running?")

    while True:
        print(MENU)
        choice = input("Choose an option: ").strip()
        if choice == "0":
            print("Goodbye!")
            sys.exit(0)
        action = ACTIONS.get(choice)
        if action is None:
            print("Invalid option.")
            continue
        try:
            action()
        except requests.RequestException as exc:
            print("Network error talking to API:", exc)


if __name__ == "__main__":
    main()

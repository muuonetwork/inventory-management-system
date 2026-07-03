import os

from flask import Flask, jsonify, request

import database
import external_api


def create_app(db_path: str = None) -> Flask:
    app = Flask(__name__)

    db_path = db_path or os.environ.get("INVENTORY_DB", "inventory.db")
    app.config["DATABASE"] = db_path

    conn = database.get_connection(db_path)
    database.init_db(conn)
    app.config["DB_CONN"] = conn

    def db():
        return app.config["DB_CONN"]

    def error(message: str, status: int = 400):
        return jsonify({"error": message}), status

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "inventory-management-system"})

    @app.get("/api/items")
    def list_items():
        name = request.args.get("name")
        category = request.args.get("category")
        if name or category:
            items = database.search_items(db(), name=name, category=category)
        else:
            items = database.get_all_items(db())
        return jsonify(items)

    @app.get("/api/items/<int:item_id>")
    def get_item(item_id):
        item = database.get_item(db(), item_id)
        if item is None:
            return error("Item not found", 404)
        return jsonify(item)

    @app.post("/api/items")
    def create_item():
        payload = request.get_json(silent=True)
        if not payload:
            return error("Request body must be JSON")
        if not payload.get("name"):
            return error("'name' is required")

        item = database.create_item(db(), payload)
        return jsonify(item), 201

    @app.patch("/api/items/<int:item_id>")
    def patch_item(item_id):
        payload = request.get_json(silent=True)
        if not payload:
            return error("Request body must be JSON")

        item = database.update_item(db(), item_id, payload)
        if item is None:
            return error("Item not found", 404)
        return jsonify(item)

    @app.delete("/api/items/<int:item_id>")
    def remove_item(item_id):
        deleted = database.delete_item(db(), item_id)
        if not deleted:
            return error("Item not found", 404)
        return jsonify({"deleted": True, "id": item_id})

    @app.get("/api/external/barcode/<barcode>")
    def external_barcode(barcode):
        try:
            product = external_api.fetch_by_barcode(barcode)
        except external_api.ExternalAPIError as exc:
            return error(str(exc), 502)

        if product is None:
            return error("Product not found in OpenFoodFacts", 404)
        return jsonify(product)

    @app.get("/api/external/search")
    def external_search():
        name = request.args.get("name")
        if not name:
            return error("Query parameter 'name' is required")
        try:
            products = external_api.search_by_name(name)
        except external_api.ExternalAPIError as exc:
            return error(str(exc), 502)
        return jsonify(products)

    @app.post("/api/items/import")
    def import_item():
        """Body: {"barcode": "..."} OR {"name": "...", "index": 0}.
        Any extra fields (e.g. "quantity", "price") get merged in before saving.
        """
        payload = request.get_json(silent=True) or {}
        barcode = payload.get("barcode")
        name = payload.get("name")

        try:
            if barcode:
                product = external_api.fetch_by_barcode(barcode)
                if product is None:
                    return error("Product not found in OpenFoodFacts", 404)
            elif name:
                results = external_api.search_by_name(name)
                if not results:
                    return error("No products found in OpenFoodFacts", 404)
                index = int(payload.get("index", 0))
                if index < 0 or index >= len(results):
                    return error(f"'index' out of range (0-{len(results) - 1})")
                product = results[index]
            else:
                return error("Provide either 'barcode' or 'name'")
        except external_api.ExternalAPIError as exc:
            return error(str(exc), 502)

        for key in ("price", "quantity", "category", "description", "name"):
            if key in payload:
                product[key] = payload[key]

        item = database.create_item(db(), product)
        return jsonify(item), 201

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(debug=True, port=5000)

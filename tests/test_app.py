"""
tests/test_app.py
------------------
Unit tests for the Flask REST API (routing + CRUD behavior).

External API calls are mocked with unittest.mock so these tests run
fast, deterministically, and without network access.
"""
import os
import tempfile
import unittest
from unittest.mock import patch

from app import create_app


class InventoryAPITestCase(unittest.TestCase):
    def setUp(self):
        # Fresh temp SQLite file per test so tests never interfere with each other.
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.app = create_app(db_path=self.db_path)
        self.client = self.app.test_client()

    def tearDown(self):
        self.app.config["DB_CONN"].close()
        os.remove(self.db_path)

    # ------------------------------------------------------------------ #
    # Health / routing sanity
    # ------------------------------------------------------------------ #
    def test_health_route(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "ok")

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def test_create_item_success(self):
        resp = self.client.post("/api/items", json={
            "name": "Widget",
            "category": "Tools",
            "quantity": 10,
            "price": 4.99,
        })
        self.assertEqual(resp.status_code, 201)
        body = resp.get_json()
        self.assertEqual(body["name"], "Widget")
        self.assertEqual(body["quantity"], 10)
        self.assertIn("id", body)

    def test_create_item_missing_name_fails(self):
        resp = self.client.post("/api/items", json={"quantity": 5})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

    def test_create_item_requires_json_body(self):
        resp = self.client.post("/api/items", data="not json")
        self.assertEqual(resp.status_code, 400)

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def test_list_items_empty(self):
        resp = self.client.get("/api/items")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), [])

    def test_list_items_after_create(self):
        self.client.post("/api/items", json={"name": "Gadget"})
        self.client.post("/api/items", json={"name": "Gizmo"})
        resp = self.client.get("/api/items")
        self.assertEqual(len(resp.get_json()), 2)

    def test_get_single_item(self):
        created = self.client.post("/api/items", json={"name": "Widget"}).get_json()
        resp = self.client.get(f"/api/items/{created['id']}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["name"], "Widget")

    def test_get_item_not_found(self):
        resp = self.client.get("/api/items/9999")
        self.assertEqual(resp.status_code, 404)

    def test_search_items_by_name(self):
        self.client.post("/api/items", json={"name": "Blue Widget"})
        self.client.post("/api/items", json={"name": "Red Gadget"})
        resp = self.client.get("/api/items?name=Widget")
        results = resp.get_json()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Blue Widget")

    # ------------------------------------------------------------------ #
    # UPDATE (PATCH)
    # ------------------------------------------------------------------ #
    def test_patch_item_updates_fields(self):
        created = self.client.post("/api/items", json={"name": "Widget", "quantity": 1}).get_json()
        resp = self.client.patch(f"/api/items/{created['id']}", json={"quantity": 99})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["quantity"], 99)
        # unrelated fields stay the same
        self.assertEqual(resp.get_json()["name"], "Widget")

    def test_patch_item_not_found(self):
        resp = self.client.patch("/api/items/12345", json={"quantity": 1})
        self.assertEqual(resp.status_code, 404)

    # ------------------------------------------------------------------ #
    # DELETE
    # ------------------------------------------------------------------ #
    def test_delete_item(self):
        created = self.client.post("/api/items", json={"name": "Widget"}).get_json()
        resp = self.client.delete(f"/api/items/{created['id']}")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["deleted"])

        # confirm it's actually gone
        follow_up = self.client.get(f"/api/items/{created['id']}")
        self.assertEqual(follow_up.status_code, 404)

    def test_delete_item_not_found(self):
        resp = self.client.delete("/api/items/424242")
        self.assertEqual(resp.status_code, 404)

    # ------------------------------------------------------------------ #
    # EXTERNAL API integration (mocked)
    # ------------------------------------------------------------------ #
    @patch("app.external_api.fetch_by_barcode")
    def test_external_barcode_lookup(self, mock_fetch):
        mock_fetch.return_value = {
            "name": "Nutella",
            "barcode": "3017620422003",
            "category": "Spreads",
            "description": "Hazelnut spread",
            "image_url": "http://example.com/img.jpg",
            "price": 0.0,
            "quantity": 0,
            "source": "openfoodfacts",
        }
        resp = self.client.get("/api/external/barcode/3017620422003")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["name"], "Nutella")
        mock_fetch.assert_called_once_with("3017620422003")

    @patch("app.external_api.fetch_by_barcode")
    def test_external_barcode_not_found(self, mock_fetch):
        mock_fetch.return_value = None
        resp = self.client.get("/api/external/barcode/000000")
        self.assertEqual(resp.status_code, 404)

    @patch("app.external_api.search_by_name")
    def test_external_search(self, mock_search):
        mock_search.return_value = [
            {"name": "Peanut Butter", "barcode": "111", "category": "Spreads",
             "description": "", "image_url": None, "price": 0.0, "quantity": 0,
             "source": "openfoodfacts"}
        ]
        resp = self.client.get("/api/external/search?name=peanut")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.get_json()), 1)

    def test_external_search_requires_name(self):
        resp = self.client.get("/api/external/search")
        self.assertEqual(resp.status_code, 400)

    @patch("app.external_api.fetch_by_barcode")
    def test_import_item_by_barcode_saves_to_db(self, mock_fetch):
        mock_fetch.return_value = {
            "name": "Nutella",
            "barcode": "3017620422003",
            "category": "Spreads",
            "description": "Hazelnut spread",
            "image_url": None,
            "price": 0.0,
            "quantity": 0,
            "source": "openfoodfacts",
        }
        resp = self.client.post("/api/items/import", json={
            "barcode": "3017620422003",
            "price": 3.49,
            "quantity": 20,
        })
        self.assertEqual(resp.status_code, 201)
        body = resp.get_json()
        self.assertEqual(body["name"], "Nutella")
        self.assertEqual(body["price"], 3.49)
        self.assertEqual(body["quantity"], 20)

        # it should now show up in the regular inventory listing
        listing = self.client.get("/api/items").get_json()
        self.assertEqual(len(listing), 1)

    def test_import_item_requires_barcode_or_name(self):
        resp = self.client.post("/api/items/import", json={})
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()

"""
tests/test_external_api.py
---------------------------
Unit tests for the OpenFoodFacts integration and the database layer,
tested in isolation from Flask.
"""
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import database
import external_api


class ExternalAPITestCase(unittest.TestCase):
    @patch("external_api.requests.get")
    def test_fetch_by_barcode_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": 1,
            "product": {
                "product_name": "Nutella",
                "code": "3017620422003",
                "categories": "Spreads, Sweet spreads",
                "generic_name": "Hazelnut spread",
                "image_url": "http://example.com/img.jpg",
            },
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        product = external_api.fetch_by_barcode("3017620422003")
        self.assertEqual(product["name"], "Nutella")
        self.assertEqual(product["category"], "Spreads")
        self.assertEqual(product["barcode"], "3017620422003")

    @patch("external_api.requests.get")
    def test_fetch_by_barcode_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": 0}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        product = external_api.fetch_by_barcode("000000")
        self.assertIsNone(product)

    @patch("external_api.requests.get")
    def test_search_by_name(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "products": [
                {"product_name": "Peanut Butter", "code": "111", "categories": "Spreads"},
                {"product_name": "Almond Butter", "code": "222", "categories": "Spreads"},
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        results = external_api.search_by_name("butter")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["name"], "Peanut Butter")

    @patch("external_api.requests.get")
    def test_network_failure_raises_external_api_error(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError("boom")

        with self.assertRaises(external_api.ExternalAPIError):
            external_api.fetch_by_barcode("123")


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.conn = database.get_connection(self.db_path)
        database.init_db(self.conn)

    def tearDown(self):
        self.conn.close()
        os.remove(self.db_path)

    def test_create_and_get_item(self):
        item = database.create_item(self.conn, {"name": "Widget", "quantity": 5, "price": 1.5})
        fetched = database.get_item(self.conn, item["id"])
        self.assertEqual(fetched["name"], "Widget")
        self.assertEqual(fetched["quantity"], 5)

    def test_update_item(self):
        item = database.create_item(self.conn, {"name": "Widget"})
        updated = database.update_item(self.conn, item["id"], {"quantity": 42})
        self.assertEqual(updated["quantity"], 42)

    def test_update_nonexistent_item_returns_none(self):
        result = database.update_item(self.conn, 999, {"quantity": 1})
        self.assertIsNone(result)

    def test_delete_item(self):
        item = database.create_item(self.conn, {"name": "Widget"})
        self.assertTrue(database.delete_item(self.conn, item["id"]))
        self.assertIsNone(database.get_item(self.conn, item["id"]))

    def test_search_items_by_name(self):
        database.create_item(self.conn, {"name": "Blue Widget"})
        database.create_item(self.conn, {"name": "Red Gadget"})
        results = database.search_items(self.conn, name="Widget")
        self.assertEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()

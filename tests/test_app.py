import os
import unittest


class FakeTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item):
        self.items[Item["id"]] = Item
        return {}

    def get_item(self, Key):
        item = self.items.get(Key["id"])
        return {"Item": item} if item else {}

    def delete_item(self, Key):
        self.items.pop(Key["id"], None)
        return {}


def _event(method, path, body=None, headers=None, path_params=None):
    return {
        "version": "2.0",
        "rawPath": path,
        "headers": headers or {},
        "requestContext": {"requestId": "req-1", "http": {"method": method, "path": path}},
        "pathParameters": path_params or {},
        "body": body,
        "isBase64Encoded": False,
    }


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["ITEMS_TABLE_NAME"] = "dummy"

        # Import after setting env var (module reads env at import time)
        from src import app  # noqa: E402

        cls.app = app

    def setUp(self):
        self.table = FakeTable()
        self.app._table = self.table  # patch module-level table

    def test_health(self):
        resp = self.app.handler(_event("GET", "/health"), None)
        self.assertEqual(resp["statusCode"], 200)

    def test_create_and_get_item(self):
        create = self.app.handler(_event("POST", "/items", body='{"name":"abc"}'), None)
        self.assertEqual(create["statusCode"], 201)

        item_id = self.app.json.loads(create["body"])["item"]["id"]
        get = self.app.handler(_event("GET", f"/items/{item_id}", path_params={"id": item_id}), None)
        self.assertEqual(get["statusCode"], 200)

    def test_create_requires_name(self):
        resp = self.app.handler(_event("POST", "/items", body="{}"), None)
        self.assertEqual(resp["statusCode"], 400)

    def test_delete_returns_204(self):
        create = self.app.handler(_event("POST", "/items", body='{"name":"abc"}'), None)
        item_id = self.app.json.loads(create["body"])["item"]["id"]

        delete = self.app.handler(_event("DELETE", f"/items/{item_id}", path_params={"id": item_id}), None)
        self.assertEqual(delete["statusCode"], 204)
        self.assertNotIn("body", delete)




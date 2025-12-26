import os
import unittest


class AuthorizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Import module once
        from src import authorizer  # noqa: E402

        cls.auth = authorizer

    def test_authorizes_when_token_matches_env(self):
        os.environ["AUTH_TOKEN"] = "secret"
        event = {"headers": {"Authorization": "Bearer secret"}}
        resp = self.auth.handler(event, None)
        self.assertTrue(resp["isAuthorized"])

    def test_denies_when_missing_token(self):
        os.environ["AUTH_TOKEN"] = "secret"
        event = {"headers": {}}
        resp = self.auth.handler(event, None)
        self.assertFalse(resp["isAuthorized"])




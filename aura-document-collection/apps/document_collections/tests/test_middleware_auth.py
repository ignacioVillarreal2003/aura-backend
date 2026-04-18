from django.test import Client, TestCase


class AuthenticationMiddlewareTests(TestCase):
    def test_protected_route_without_credentials_returns_missing_token(self):
        client = Client()
        response = client.get("/api/v1/document-collections/")
        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertEqual(body["error"], "missing_token")
        self.assertIn("WWW-Authenticate", response)

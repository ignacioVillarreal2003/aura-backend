from django.test import Client, TestCase


class HealthEndpointTests(TestCase):
    def test_health_ok(self):
        client = Client()
        response = client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

from django.test import RequestFactory, TestCase, override_settings

from core.authentication.authenticated_user import AuthenticatedUser
from core.authentication.exceptions import ServiceAuthenticationRejected
from core.authentication.provider import AuthenticationProvider


@override_settings(SERVICE_API_KEY="correct-key")
class AuthenticationProviderServiceAuthTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.provider = AuthenticationProvider()

    def test_no_service_headers_returns_none(self):
        request = self.factory.get("/api/v1/document-collections/")
        self.assertIsNone(self.provider.evaluate_service_auth(request))

    def test_empty_service_key_raises_401(self):
        request = self.factory.get(
            "/api/v1/document-collections/",
            HTTP_X_SERVICE_API_KEY="",
        )
        with self.assertRaises(ServiceAuthenticationRejected) as ctx:
            self.provider.evaluate_service_auth(request)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.error, "missing_service_key")

    def test_invalid_service_key_raises_403(self):
        request = self.factory.get(
            "/api/v1/document-collections/",
            HTTP_X_SERVICE_API_KEY="incorrect-k",
            HTTP_X_USER_ID="1",
            HTTP_X_USER_EMAIL="a@b.com",
        )
        with self.assertRaises(ServiceAuthenticationRejected) as ctx:
            self.provider.evaluate_service_auth(request)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.error, "invalid_service_key")

    def test_missing_user_id_raises_400(self):
        request = self.factory.get(
            "/api/v1/document-collections/",
            HTTP_X_SERVICE_API_KEY="correct-key",
            HTTP_X_USER_EMAIL="a@b.com",
        )
        with self.assertRaises(ServiceAuthenticationRejected) as ctx:
            self.provider.evaluate_service_auth(request)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.error, "missing_user_id")

    def test_invalid_user_id_raises_400(self):
        request = self.factory.get(
            "/api/v1/document-collections/",
            HTTP_X_SERVICE_API_KEY="correct-key",
            HTTP_X_USER_ID="not-int",
            HTTP_X_USER_EMAIL="a@b.com",
        )
        with self.assertRaises(ServiceAuthenticationRejected) as ctx:
            self.provider.evaluate_service_auth(request)
        self.assertEqual(ctx.exception.error, "invalid_user_id")

    def test_missing_email_raises_400(self):
        request = self.factory.get(
            "/api/v1/document-collections/",
            HTTP_X_SERVICE_API_KEY="correct-key",
            HTTP_X_USER_ID="42",
        )
        with self.assertRaises(ServiceAuthenticationRejected) as ctx:
            self.provider.evaluate_service_auth(request)
        self.assertEqual(ctx.exception.error, "missing_user_email")

    def test_valid_service_auth_returns_user(self):
        request = self.factory.get(
            "/api/v1/document-collections/",
            HTTP_X_SERVICE_API_KEY="correct-key",
            HTTP_X_USER_ID="42",
            HTTP_X_USER_EMAIL="owner@example.com",
            HTTP_X_USER_ROLES="ADMIN, USER",
            HTTP_X_USER_PERMISSIONS="DOCUMENT_GET",
        )
        user = self.provider.evaluate_service_auth(request)
        self.assertIsInstance(user, AuthenticatedUser)
        self.assertEqual(user.id, 42)
        self.assertEqual(user.email, "owner@example.com")
        self.assertEqual(user.roles, ["ADMIN", "USER"])
        self.assertEqual(user.permissions, ["DOCUMENT_GET"])

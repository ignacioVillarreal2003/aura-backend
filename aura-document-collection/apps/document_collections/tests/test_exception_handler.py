from django.test import TestCase

from apps.document_collections.exceptions import DuplicateMembershipException
from core.exceptions.handler import custom_exception_handler


class CustomExceptionHandlerTests(TestCase):
    def test_conflict_returns_409_body(self):
        exc = DuplicateMembershipException()
        response = custom_exception_handler(exc, {"view": None})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"], "duplicate_membership")
        self.assertEqual(response.data["status_code"], 409)

import pytest
from django.conf import settings

from apps.accounts.models import User


@pytest.fixture
def bootstrap_user(db):
    return User.objects.create_superuser("admin", "admin@example.com", "adminpass")


@pytest.fixture
def regular_user(bootstrap_user):
    return User.objects.create_user(
        "testuser", "test@example.com", "testpass123", created_by=bootstrap_user
    )


@pytest.fixture
def svc_headers():
    return {"HTTP_X_SERVICE_API_KEY": settings.SERVICE_API_KEY}

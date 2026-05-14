from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from core.authentication.authenticated_user import AuthenticatedUser


# ---------------------------------------------------------------------------
# Object factories
# ---------------------------------------------------------------------------

def make_user(user_id=1, permissions=("*",), roles=("admin",), email=None):
    return AuthenticatedUser(
        id=user_id,
        email=email or f"user{user_id}@example.com",
        username=f"user{user_id}",
        roles=tuple(roles),
        permissions=tuple(permissions),
    )


def make_classification_level(level_id=1, name="TOP SECRET", rank=5):
    return SimpleNamespace(id=level_id, name=name, rank=rank)


def make_compartment(compartment_id=1, name="ALPHA", description="Alpha compartment"):
    return SimpleNamespace(id=compartment_id, name=name, description=description)


def make_document_collection(collection_id=1, name="Test Collection", created_by=1, **overrides):
    now = timezone.now()
    data = dict(
        id=collection_id,
        name=name,
        classification_level=make_classification_level(),
        compartments=[make_compartment()],
        created_by=created_by,
        created_at=now,
        updated_by=None,
        updated_at=None,
        deleted_at=None,
        deleted_by=None,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_document(document_id=1, name="Test Document", deleted_at=None):
    return SimpleNamespace(id=document_id, name=name, deleted_at=deleted_at)


def make_document_link(link_id=1, collection_id=1, document_id=1, created_by=1, **overrides):
    now = timezone.now()
    data = dict(
        id=link_id,
        document_collection_id=collection_id,
        document=make_document(document_id=document_id),
        created_by=created_by,
        created_at=now,
        deleted_at=None,
        deleted_by=None,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_user_clearance(clearance_id=1, user_id=10, classification_level_id=1, created_by=1):
    now = timezone.now()
    return SimpleNamespace(
        id=clearance_id,
        user_id=user_id,
        classification_level=make_classification_level(level_id=classification_level_id),
        created_by=created_by,
        created_at=now,
    )


def make_user_compartment(uc_id=1, user_id=10, compartment_id=1, created_by=1):
    now = timezone.now()
    return SimpleNamespace(
        id=uc_id,
        user_id=user_id,
        compartment=make_compartment(compartment_id=compartment_id),
        created_by=created_by,
        created_at=now,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def user():
    return make_user()


@pytest.fixture
def mock_validate_token(mocker, user):
    return mocker.patch(
        "core.authentication.authentication_provider.authentication_provider.validate_token",
        return_value=user,
    )


@pytest.fixture
def api_client(mock_validate_token):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer test_token")
    return client


@pytest.fixture
def anon_client():
    return APIClient()

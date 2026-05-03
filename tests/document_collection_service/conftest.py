"""
Fixtures compartidas para los tests funcionales del aura-document-collection-service.

Estrategia:
- Se remueve AuthenticationMiddleware en settings_test y se usa force_authenticate
  para inyectar el usuario, evitando llamadas al auth provider externo.
- Se parchean los singletons de servicio para evitar acceso real a la BD.
- Los objetos de dominio usan SimpleNamespace para que los serializers de DRF
  puedan acceder los atributos sin necesidad de instancias reales del modelo.
"""

import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

_svc = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "aura-document-collection-service")
)
if _svc not in sys.path:
    sys.path.insert(0, _svc)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings_test")

import django
from django.test.utils import setup_test_environment

django.setup()
setup_test_environment()

import pytest
from rest_framework.test import APIClient

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import permissions as perm
from core.integrations.user_profile_client import UserProfile, UserProfilesResult

USER_ID = 1
USER_EMAIL = "admin@test.com"
NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)

ALL_PERMISSIONS = frozenset({
    perm.LIST_DOCUMENT_COLLECTIONS,
    perm.CREATE_DOCUMENT_COLLECTION,
    perm.GET_DOCUMENT_COLLECTION,
    perm.UPDATE_DOCUMENT_COLLECTION,
    perm.DELETE_DOCUMENT_COLLECTION,
    perm.LIST_DOCUMENT_COLLECTION_USERS,
    perm.ADD_DOCUMENT_COLLECTION_USER,
    perm.REMOVE_DOCUMENT_COLLECTION_USER,
    perm.LIST_DOCUMENT_COLLECTION_DOCUMENTS,
    perm.ADD_DOCUMENT_COLLECTION_DOCUMENT,
    perm.REMOVE_DOCUMENT_COLLECTION_DOCUMENT,
})


def make_collection(id=1, name="Mi Colección"):
    return SimpleNamespace(id=id, name=name, created_by=USER_ID, created_at=NOW, updated_at=None, pk=id)


def make_document_link(id=1, doc_id=10, doc_name="Documento de prueba"):
    doc = SimpleNamespace(id=doc_id, name=doc_name)
    return SimpleNamespace(id=id, created_by=USER_ID, created_at=NOW, document=doc)


def make_membership(id=1, user_id=2):
    return SimpleNamespace(id=id, user_id=user_id, created_by=USER_ID, created_at=NOW)


def make_profiles_result(user_id=2):
    profile = UserProfile(id=user_id, email="user@test.com", username="usuario2")
    return UserProfilesResult(profiles={user_id: profile}, enrichment="complete")


@pytest.fixture
def mock_collection_service():
    with patch(
        "apps.document_collections.views.document_collection_viewset.document_collection_service"
    ) as mock:
        yield mock


@pytest.fixture
def mock_document_service():
    with patch(
        "apps.document_collection_documents.views.document_collection_document_viewset.document_collection_document_service"
    ) as mock:
        yield mock


@pytest.fixture
def mock_user_service():
    with patch(
        "apps.document_collection_users.views.document_collection_user_viewset.document_collection_user_service"
    ) as mock:
        yield mock


@pytest.fixture
def mock_profile_client():
    with patch(
        "apps.document_collection_users.views.document_collection_user_viewset.user_profile_client"
    ) as mock:
        mock.fetch_by_ids.return_value = make_profiles_result()
        yield mock


@pytest.fixture
def client(mock_collection_service, mock_document_service, mock_user_service, mock_profile_client):
    api_client = APIClient()
    api_client.force_authenticate(user=AuthenticatedUser(
        id=USER_ID,
        email=USER_EMAIL,
        permissions=list(ALL_PERMISSIONS),
    ))
    return api_client

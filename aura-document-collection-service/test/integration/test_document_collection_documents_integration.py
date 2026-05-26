import pytest

from apps.classification_levels.services.classification_level_service import classification_level_service
from apps.compartments.services.compartment_service import compartment_service
from apps.document_collection_documents.models import Document, DocumentInDocumentCollection
from apps.document_collection_documents.services.document_collection_document_service import (
    document_collection_document_service,
)
from apps.document_collections.services.document_collection_service import document_collection_service
from core.domain.document_collection_exceptions import (
    CollectionNotFoundException,
    DocumentLinkNotFoundException,
    DocumentNotAvailableException,
    DuplicateDocumentLinkException,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def level(admin):
    return classification_level_service.create_classification_level(admin, name="TEST_SECRET", rank=1003)


@pytest.fixture
def compartment(admin):
    return compartment_service.create_compartment(admin, name="TEST_ALPHA", description="")


@pytest.fixture
def collection(admin, level, compartment):
    return document_collection_service.create_document_collection(
        admin,
        name="TEST_Doc_Test_Collection",
        classification_level_id=level.id,
        compartment_ids=[compartment.id],
    )


_DOC_DEFAULTS = dict(
    mime_type="application/octet-stream",
    storage_url="test://placeholder",
    file_size_bytes=0,
    created_by=1,
)


@pytest.fixture
def document():
    return Document.objects.create(name="TEST_Test_Document", **_DOC_DEFAULTS)


@pytest.fixture
def deleted_document():
    from django.utils import timezone
    return Document.objects.create(
        name="TEST_Deleted_Document",
        deleted_at=timezone.now(),
        **_DOC_DEFAULTS,
    )


# ---------------------------------------------------------------------------
# list_document_collection_documents
# ---------------------------------------------------------------------------

def test_list_documents_returns_active_links(admin, collection, document):
    document_collection_document_service.add_document_collection_document(
        admin, collection.id, document_id=document.id
    )
    qs = document_collection_document_service.list_document_collection_documents(admin, collection.id)
    assert qs.filter(document_id=document.id).exists()


def test_list_documents_excludes_removed_links(admin, collection, document):
    document_collection_document_service.add_document_collection_document(
        admin, collection.id, document_id=document.id
    )
    document_collection_document_service.remove_document_collection_document(
        admin, collection.id, document.id
    )
    qs = document_collection_document_service.list_document_collection_documents(admin, collection.id)
    assert not qs.filter(document_id=document.id).exists()


def test_list_documents_collection_not_found_raises(admin):
    with pytest.raises(CollectionNotFoundException):
        document_collection_document_service.list_document_collection_documents(admin, 999999)


# ---------------------------------------------------------------------------
# add_document_collection_document
# ---------------------------------------------------------------------------

def test_add_document_persists_link(admin, collection, document):
    link = document_collection_document_service.add_document_collection_document(
        admin, collection.id, document_id=document.id
    )
    assert DocumentInDocumentCollection.objects.filter(id=link.id).exists()


def test_add_document_sets_created_by(admin, collection, document):
    link = document_collection_document_service.add_document_collection_document(
        admin, collection.id, document_id=document.id
    )
    assert link.created_by == admin.id


def test_add_document_collection_not_found_raises(admin, document):
    with pytest.raises(CollectionNotFoundException):
        document_collection_document_service.add_document_collection_document(
            admin, 999999, document_id=document.id
        )


def test_add_document_nonexistent_raises(admin, collection):
    with pytest.raises(DocumentNotAvailableException):
        document_collection_document_service.add_document_collection_document(
            admin, collection.id, document_id=999999
        )


def test_add_deleted_document_raises(admin, collection, deleted_document):
    with pytest.raises(DocumentNotAvailableException):
        document_collection_document_service.add_document_collection_document(
            admin, collection.id, document_id=deleted_document.id
        )


def test_add_document_duplicate_raises(admin, collection, document):
    document_collection_document_service.add_document_collection_document(
        admin, collection.id, document_id=document.id
    )
    with pytest.raises(DuplicateDocumentLinkException):
        document_collection_document_service.add_document_collection_document(
            admin, collection.id, document_id=document.id
        )


# ---------------------------------------------------------------------------
# remove_document_collection_document
# ---------------------------------------------------------------------------

def test_remove_document_soft_deletes_link(admin, collection, document):
    document_collection_document_service.add_document_collection_document(
        admin, collection.id, document_id=document.id
    )
    document_collection_document_service.remove_document_collection_document(
        admin, collection.id, document.id
    )
    assert not DocumentInDocumentCollection.objects.filter(
        document_collection_id=collection.id,
        document_id=document.id,
    ).exists()
    assert DocumentInDocumentCollection.objects.all_with_deleted().filter(
        document_collection_id=collection.id,
        document_id=document.id,
        deleted_at__isnull=False,
    ).exists()


def test_remove_document_collection_not_found_raises(admin, document):
    with pytest.raises(CollectionNotFoundException):
        document_collection_document_service.remove_document_collection_document(
            admin, 999999, document.id
        )


def test_remove_document_link_not_found_raises(admin, collection, document):
    with pytest.raises(DocumentLinkNotFoundException):
        document_collection_document_service.remove_document_collection_document(
            admin, collection.id, document.id
        )

import pytest

from apps.classification_levels.services.classification_level_service import classification_level_service
from apps.compartments.services.compartment_service import compartment_service
from apps.document_collections.models import DocumentCollection
from apps.document_collections.services.document_collection_service import document_collection_service
from core.domain.document_collection_exceptions import (
    ClassificationLevelNotFoundException,
    CollectionNotFoundException,
    CompartmentNotFoundException,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def level(admin):
    return classification_level_service.create_classification_level(admin, name="TEST_SECRET", rank=1003)


@pytest.fixture
def level2(admin):
    return classification_level_service.create_classification_level(admin, name="TEST_TOP_SECRET", rank=1005)


@pytest.fixture
def compartment_a(admin):
    return compartment_service.create_compartment(admin, name="TEST_ALPHA", description="")


@pytest.fixture
def compartment_b(admin):
    return compartment_service.create_compartment(admin, name="TEST_BRAVO", description="")


@pytest.fixture
def collection(admin, level, compartment_a):
    return document_collection_service.create_document_collection(
        admin,
        name="TEST_Test_Collection",
        classification_level_id=level.id,
        compartment_ids=[compartment_a.id],
    )


# ---------------------------------------------------------------------------
# create_document_collection
# ---------------------------------------------------------------------------

def test_create_document_collection_persists_to_db(admin, level, compartment_a):
    collection = document_collection_service.create_document_collection(
        admin,
        name="TEST_My_Collection",
        classification_level_id=level.id,
        compartment_ids=[compartment_a.id],
    )
    assert DocumentCollection.objects.filter(id=collection.id, name="TEST_My_Collection").exists()


def test_create_document_collection_sets_created_by(admin, level, compartment_a):
    collection = document_collection_service.create_document_collection(
        admin,
        name="TEST_Audit_Test",
        classification_level_id=level.id,
        compartment_ids=[compartment_a.id],
    )
    assert collection.created_by == admin.id


def test_create_document_collection_links_compartments(admin, level, compartment_a, compartment_b):
    collection = document_collection_service.create_document_collection(
        admin,
        name="TEST_Multi_Compartment",
        classification_level_id=level.id,
        compartment_ids=[compartment_a.id, compartment_b.id],
    )
    linked_ids = set(collection.compartments.values_list("id", flat=True))
    assert compartment_a.id in linked_ids
    assert compartment_b.id in linked_ids


def test_create_document_collection_deduplicates_compartment_ids(admin, level, compartment_a):
    collection = document_collection_service.create_document_collection(
        admin,
        name="TEST_Dedup_Test",
        classification_level_id=level.id,
        compartment_ids=[compartment_a.id, compartment_a.id],
    )
    assert collection.compartments.count() == 1


def test_create_document_collection_invalid_classification_level_raises(admin, compartment_a):
    with pytest.raises(ClassificationLevelNotFoundException):
        document_collection_service.create_document_collection(
            admin,
            name="TEST_Bad_Level",
            classification_level_id=999999,
            compartment_ids=[compartment_a.id],
        )


def test_create_document_collection_invalid_compartment_raises(admin, level):
    with pytest.raises(CompartmentNotFoundException):
        document_collection_service.create_document_collection(
            admin,
            name="TEST_Bad_Compartment",
            classification_level_id=level.id,
            compartment_ids=[999999],
        )


# ---------------------------------------------------------------------------
# get_document_collection
# ---------------------------------------------------------------------------

def test_get_document_collection_returns_correct_object(admin, collection):
    fetched = document_collection_service.get_document_collection(admin, collection.id)
    assert fetched.id == collection.id
    assert fetched.name == "TEST_Test_Collection"


def test_get_document_collection_not_found_raises(admin):
    with pytest.raises(CollectionNotFoundException):
        document_collection_service.get_document_collection(admin, 999999)


def test_get_document_collection_deleted_raises(admin, collection):
    document_collection_service.delete_document_collection(admin, collection.id)
    with pytest.raises(CollectionNotFoundException):
        document_collection_service.get_document_collection(admin, collection.id)


# ---------------------------------------------------------------------------
# update_document_collection
# ---------------------------------------------------------------------------

def test_update_document_collection_name(admin, collection):
    document_collection_service.update_document_collection(admin, collection.id, name="TEST_Renamed")
    collection.refresh_from_db()
    assert collection.name == "TEST_Renamed"


def test_update_document_collection_sets_updated_by(admin, collection):
    document_collection_service.update_document_collection(admin, collection.id, name="TEST_Updated")
    collection.refresh_from_db()
    assert collection.updated_by == admin.id


def test_update_document_collection_classification_level(admin, collection, level2):
    document_collection_service.update_document_collection(
        admin, collection.id, classification_level_id=level2.id
    )
    collection.refresh_from_db()
    assert collection.classification_level_id == level2.id


def test_update_document_collection_replaces_compartments(admin, collection, compartment_b):
    document_collection_service.update_document_collection(
        admin, collection.id, compartment_ids=[compartment_b.id]
    )
    linked_ids = list(collection.compartments.values_list("id", flat=True))
    assert linked_ids == [compartment_b.id]


def test_update_document_collection_not_found_raises(admin):
    with pytest.raises(CollectionNotFoundException):
        document_collection_service.update_document_collection(admin, 999999, name="Ghost")


def test_update_document_collection_invalid_classification_level_raises(admin, collection):
    with pytest.raises(ClassificationLevelNotFoundException):
        document_collection_service.update_document_collection(
            admin, collection.id, classification_level_id=999999
        )


def test_update_document_collection_invalid_compartment_raises(admin, collection):
    with pytest.raises(CompartmentNotFoundException):
        document_collection_service.update_document_collection(
            admin, collection.id, compartment_ids=[999999]
        )


# ---------------------------------------------------------------------------
# delete_document_collection
# ---------------------------------------------------------------------------

def test_delete_document_collection_soft_deletes(admin, collection):
    collection_id = collection.id
    document_collection_service.delete_document_collection(admin, collection_id)
    assert not DocumentCollection.objects.filter(id=collection_id).exists()
    assert DocumentCollection.objects.all_with_deleted().filter(
        id=collection_id, deleted_at__isnull=False
    ).exists()


def test_delete_document_collection_sets_deleted_by(admin, collection):
    collection_id = collection.id
    document_collection_service.delete_document_collection(admin, collection_id)
    deleted = DocumentCollection.objects.all_with_deleted().get(id=collection_id)
    assert deleted.deleted_by == admin.id


def test_delete_document_collection_not_found_raises(admin):
    with pytest.raises(CollectionNotFoundException):
        document_collection_service.delete_document_collection(admin, 999999)

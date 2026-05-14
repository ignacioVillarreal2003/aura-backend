import pytest

from apps.classification_levels.services.classification_level_service import classification_level_service
from apps.compartments.services.compartment_service import compartment_service
from apps.document_collections.services.document_collection_service import document_collection_service
from apps.user_authorizations.models import UserClearance, UserCompartment
from apps.user_authorizations.services.user_authorization_service import user_authorization_service
from core.domain.document_collection_exceptions import (
    DuplicateUserCompartmentException,
    UserClearanceNotFoundException,
    UserCompartmentNotFoundException,
)

pytestmark = pytest.mark.django_db

_TARGET_USER_ID = 500


@pytest.fixture
def level(admin):
    return classification_level_service.create_classification_level(admin, name="TEST_SECRET", rank=1003)


@pytest.fixture
def level_high(admin):
    return classification_level_service.create_classification_level(admin, name="TEST_TOP_SECRET", rank=1005)


@pytest.fixture
def compartment(admin):
    return compartment_service.create_compartment(admin, name="TEST_ALPHA", description="")


@pytest.fixture
def compartment_b(admin):
    return compartment_service.create_compartment(admin, name="TEST_BRAVO", description="")


@pytest.fixture
def collection(admin, level, compartment):
    return document_collection_service.create_document_collection(
        admin,
        name="TEST_MAC_Collection",
        classification_level_id=level.id,
        compartment_ids=[compartment.id],
    )


# ---------------------------------------------------------------------------
# set_user_clearance
# ---------------------------------------------------------------------------

def test_set_user_clearance_creates_row(admin, level):
    clearance = user_authorization_service.set_user_clearance(
        admin, _TARGET_USER_ID, classification_level_id=level.id
    )
    assert UserClearance.objects.filter(user_id=_TARGET_USER_ID).exists()
    assert clearance.user_id == _TARGET_USER_ID
    assert clearance.classification_level_id == level.id


def test_set_user_clearance_upserts_existing_row(admin, level, level_high):
    user_authorization_service.set_user_clearance(admin, _TARGET_USER_ID, classification_level_id=level.id)
    user_authorization_service.set_user_clearance(admin, _TARGET_USER_ID, classification_level_id=level_high.id)
    assert UserClearance.objects.filter(user_id=_TARGET_USER_ID).count() == 1
    clearance = UserClearance.objects.get(user_id=_TARGET_USER_ID)
    assert clearance.classification_level_id == level_high.id


# ---------------------------------------------------------------------------
# delete_user_clearance
# ---------------------------------------------------------------------------

def test_delete_user_clearance_removes_row(admin, level):
    user_authorization_service.set_user_clearance(admin, _TARGET_USER_ID, classification_level_id=level.id)
    user_authorization_service.delete_user_clearance(admin, _TARGET_USER_ID)
    assert not UserClearance.objects.filter(user_id=_TARGET_USER_ID).exists()


def test_delete_user_clearance_not_found_raises(admin):
    with pytest.raises(UserClearanceNotFoundException):
        user_authorization_service.delete_user_clearance(admin, _TARGET_USER_ID)


# ---------------------------------------------------------------------------
# add_user_compartment / remove_user_compartment
# ---------------------------------------------------------------------------

def test_add_user_compartment_creates_row(admin, compartment):
    uc = user_authorization_service.add_user_compartment(
        admin, _TARGET_USER_ID, compartment_id=compartment.id
    )
    assert UserCompartment.objects.filter(user_id=_TARGET_USER_ID, compartment_id=compartment.id).exists()
    assert uc.user_id == _TARGET_USER_ID


def test_add_user_compartment_duplicate_raises(admin, compartment):
    user_authorization_service.add_user_compartment(admin, _TARGET_USER_ID, compartment_id=compartment.id)
    with pytest.raises(DuplicateUserCompartmentException):
        user_authorization_service.add_user_compartment(admin, _TARGET_USER_ID, compartment_id=compartment.id)


def test_remove_user_compartment_deletes_row(admin, compartment):
    user_authorization_service.add_user_compartment(admin, _TARGET_USER_ID, compartment_id=compartment.id)
    user_authorization_service.remove_user_compartment(admin, _TARGET_USER_ID, compartment_id=compartment.id)
    assert not UserCompartment.objects.filter(user_id=_TARGET_USER_ID, compartment_id=compartment.id).exists()


def test_remove_user_compartment_not_found_raises(admin, compartment):
    with pytest.raises(UserCompartmentNotFoundException):
        user_authorization_service.remove_user_compartment(admin, _TARGET_USER_ID, compartment_id=compartment.id)


# ---------------------------------------------------------------------------
# list_user_compartments
# ---------------------------------------------------------------------------

def test_list_user_compartments_returns_entries(admin, compartment, compartment_b):
    user_authorization_service.add_user_compartment(admin, _TARGET_USER_ID, compartment_id=compartment.id)
    user_authorization_service.add_user_compartment(admin, _TARGET_USER_ID, compartment_id=compartment_b.id)
    qs = user_authorization_service.list_user_compartments(admin, _TARGET_USER_ID)
    assert qs.count() == 2


def test_list_user_compartments_empty_for_new_user(admin):
    qs = user_authorization_service.list_user_compartments(admin, _TARGET_USER_ID)
    assert qs.count() == 0


# ---------------------------------------------------------------------------
# get_user_authorization
# ---------------------------------------------------------------------------

def test_get_user_authorization_returns_clearance_and_compartments(admin, level, compartment):
    user_authorization_service.set_user_clearance(admin, _TARGET_USER_ID, classification_level_id=level.id)
    user_authorization_service.add_user_compartment(admin, _TARGET_USER_ID, compartment_id=compartment.id)
    result = user_authorization_service.get_user_authorization(admin, _TARGET_USER_ID)
    assert result["user_id"] == _TARGET_USER_ID
    assert result["clearance"] is not None
    assert len(result["compartments"]) == 1


def test_get_user_authorization_no_clearance_returns_none(admin):
    result = user_authorization_service.get_user_authorization(admin, _TARGET_USER_ID)
    assert result["clearance"] is None
    assert result["compartments"] == []


# ---------------------------------------------------------------------------
# get_accessible_collections (MAC intersection)
# ---------------------------------------------------------------------------

def test_accessible_collections_returns_matching_collection(admin, level, compartment, collection):
    user_authorization_service.set_user_clearance(admin, _TARGET_USER_ID, classification_level_id=level.id)
    user_authorization_service.add_user_compartment(admin, _TARGET_USER_ID, compartment_id=compartment.id)
    qs = user_authorization_service.get_accessible_collections(admin, _TARGET_USER_ID)
    assert qs.filter(id=collection.id).exists()


def test_accessible_collections_no_clearance_returns_empty(admin, compartment, collection):
    user_authorization_service.add_user_compartment(admin, _TARGET_USER_ID, compartment_id=compartment.id)
    qs = user_authorization_service.get_accessible_collections(admin, _TARGET_USER_ID)
    assert qs.count() == 0


def test_accessible_collections_no_compartments_returns_empty(admin, level, collection):
    user_authorization_service.set_user_clearance(admin, _TARGET_USER_ID, classification_level_id=level.id)
    qs = user_authorization_service.get_accessible_collections(admin, _TARGET_USER_ID)
    assert qs.count() == 0


def test_accessible_collections_insufficient_rank_returns_empty(admin, level, compartment, collection):
    level_low = classification_level_service.create_classification_level(admin, name="TEST_UNCLASSIFIED", rank=1001)
    user_authorization_service.set_user_clearance(admin, _TARGET_USER_ID, classification_level_id=level_low.id)
    user_authorization_service.add_user_compartment(admin, _TARGET_USER_ID, compartment_id=compartment.id)
    qs = user_authorization_service.get_accessible_collections(admin, _TARGET_USER_ID)
    assert not qs.filter(id=collection.id).exists()


def test_accessible_collections_missing_compartment_returns_empty(admin, level, compartment, compartment_b, collection):
    user_authorization_service.set_user_clearance(admin, _TARGET_USER_ID, classification_level_id=level.id)
    user_authorization_service.add_user_compartment(admin, _TARGET_USER_ID, compartment_id=compartment_b.id)
    qs = user_authorization_service.get_accessible_collections(admin, _TARGET_USER_ID)
    assert not qs.filter(id=collection.id).exists()

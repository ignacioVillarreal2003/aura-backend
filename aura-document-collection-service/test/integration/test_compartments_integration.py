import pytest

from apps.compartments.models import Compartment
from apps.compartments.services.compartment_service import compartment_service
from apps.document_collections.services.document_collection_service import document_collection_service
from apps.classification_levels.services.classification_level_service import classification_level_service
from core.domain.document_collection_exceptions import (
    CompartmentNotFoundException,
    CompartmentInUseException,
    DuplicateCompartmentException,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# create_compartment
# ---------------------------------------------------------------------------

def test_create_compartment_persists_to_db(admin):
    compartment = compartment_service.create_compartment(admin, name="TEST_ALPHA", description="Alpha unit")
    assert Compartment.objects.filter(id=compartment.id, name="TEST_ALPHA").exists()


def test_create_compartment_returns_correct_fields(admin):
    compartment = compartment_service.create_compartment(admin, name="TEST_BRAVO", description="Bravo desc")
    assert compartment.name == "TEST_BRAVO"
    assert compartment.description == "Bravo desc"


def test_create_compartment_without_description(admin):
    compartment = compartment_service.create_compartment(admin, name="TEST_CHARLIE", description="")
    assert compartment.description == ""


def test_create_compartment_duplicate_name_raises(admin):
    compartment_service.create_compartment(admin, name="TEST_DELTA", description="")
    with pytest.raises(DuplicateCompartmentException):
        compartment_service.create_compartment(admin, name="TEST_DELTA", description="dup")


# ---------------------------------------------------------------------------
# get_compartment
# ---------------------------------------------------------------------------

def test_get_compartment_returns_object(admin):
    created = compartment_service.create_compartment(admin, name="TEST_ECHO", description="")
    fetched = compartment_service.get_compartment(admin, created.id)
    assert fetched.id == created.id
    assert fetched.name == "TEST_ECHO"


def test_get_compartment_not_found_raises(admin):
    with pytest.raises(CompartmentNotFoundException):
        compartment_service.get_compartment(admin, 999999)


# ---------------------------------------------------------------------------
# update_compartment
# ---------------------------------------------------------------------------

def test_update_compartment_persists_name(admin):
    compartment = compartment_service.create_compartment(admin, name="TEST_OLD_NAME", description="")
    compartment_service.update_compartment(admin, compartment.id, name="TEST_NEW_NAME")
    compartment.refresh_from_db()
    assert compartment.name == "TEST_NEW_NAME"


def test_update_compartment_persists_description(admin):
    compartment = compartment_service.create_compartment(admin, name="TEST_FOXTROT", description="old")
    compartment_service.update_compartment(admin, compartment.id, description="updated")
    compartment.refresh_from_db()
    assert compartment.description == "updated"


def test_update_compartment_not_found_raises(admin):
    with pytest.raises(CompartmentNotFoundException):
        compartment_service.update_compartment(admin, 999999, name="X")


def test_update_compartment_duplicate_name_raises(admin):
    compartment_service.create_compartment(admin, name="TEST_TAKEN_C", description="")
    c2 = compartment_service.create_compartment(admin, name="TEST_FREE_C", description="")
    with pytest.raises(DuplicateCompartmentException):
        compartment_service.update_compartment(admin, c2.id, name="TEST_TAKEN_C")


# ---------------------------------------------------------------------------
# delete_compartment
# ---------------------------------------------------------------------------

def test_delete_compartment_removes_from_db(admin):
    compartment = compartment_service.create_compartment(admin, name="TEST_DELETE_ME_C", description="")
    compartment_id = compartment.id
    compartment_service.delete_compartment(admin, compartment_id)
    assert not Compartment.objects.filter(id=compartment_id).exists()


def test_delete_compartment_not_found_raises(admin):
    with pytest.raises(CompartmentNotFoundException):
        compartment_service.delete_compartment(admin, 999999)


def test_delete_compartment_in_use_raises(admin):
    level = classification_level_service.create_classification_level(admin, name="TEST_LEVEL_X", rank=1050)
    compartment = compartment_service.create_compartment(admin, name="TEST_IN_USE", description="")
    document_collection_service.create_document_collection(
        admin,
        name="TEST_Blocking_Collection",
        classification_level_id=level.id,
        compartment_ids=[compartment.id],
    )
    with pytest.raises(CompartmentInUseException):
        compartment_service.delete_compartment(admin, compartment.id)

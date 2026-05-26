import pytest

from apps.classification_levels.models import ClassificationLevel
from apps.classification_levels.services.classification_level_service import classification_level_service
from core.domain.document_collection_exceptions import (
    ClassificationLevelNotFoundException,
    ClassificationLevelInUseException,
    DuplicateClassificationLevelException,
)

from .conftest import make_user

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# create_classification_level
# ---------------------------------------------------------------------------

def test_create_classification_level_persists_to_db(admin):
    level = classification_level_service.create_classification_level(admin, name="TEST_TOP_SECRET", rank=1005)
    assert ClassificationLevel.objects.filter(id=level.id, name="TEST_TOP_SECRET", rank=1005).exists()


def test_create_classification_level_returns_correct_fields(admin):
    level = classification_level_service.create_classification_level(admin, name="TEST_SECRET", rank=1003)
    assert level.name == "TEST_SECRET"
    assert level.rank == 1003


def test_create_classification_level_duplicate_name_raises(admin):
    classification_level_service.create_classification_level(admin, name="TEST_UNCLASSIFIED", rank=1001)
    with pytest.raises(DuplicateClassificationLevelException):
        classification_level_service.create_classification_level(admin, name="TEST_UNCLASSIFIED", rank=1002)


def test_create_classification_level_duplicate_rank_raises(admin):
    classification_level_service.create_classification_level(admin, name="TEST_LEVEL_A", rank=1010)
    with pytest.raises(DuplicateClassificationLevelException):
        classification_level_service.create_classification_level(admin, name="TEST_LEVEL_B", rank=1010)


# ---------------------------------------------------------------------------
# get_classification_level
# ---------------------------------------------------------------------------

def test_get_classification_level_returns_object(admin):
    created = classification_level_service.create_classification_level(admin, name="TEST_CONFIDENTIAL", rank=1002)
    fetched = classification_level_service.get_classification_level(admin, created.id)
    assert fetched.id == created.id
    assert fetched.name == "TEST_CONFIDENTIAL"


def test_get_classification_level_not_found_raises(admin):
    with pytest.raises(ClassificationLevelNotFoundException):
        classification_level_service.get_classification_level(admin, 999999)


# ---------------------------------------------------------------------------
# update_classification_level
# ---------------------------------------------------------------------------

def test_update_classification_level_persists_name(admin):
    level = classification_level_service.create_classification_level(admin, name="TEST_OLD", rank=1004)
    classification_level_service.update_classification_level(admin, level.id, name="TEST_NEW")
    level.refresh_from_db()
    assert level.name == "TEST_NEW"


def test_update_classification_level_persists_rank(admin):
    level = classification_level_service.create_classification_level(admin, name="TEST_RANKER", rank=1006)
    classification_level_service.update_classification_level(admin, level.id, rank=1009)
    level.refresh_from_db()
    assert level.rank == 1009


def test_update_classification_level_not_found_raises(admin):
    with pytest.raises(ClassificationLevelNotFoundException):
        classification_level_service.update_classification_level(admin, 999999, name="X")


def test_update_classification_level_duplicate_name_raises(admin):
    classification_level_service.create_classification_level(admin, name="TEST_TAKEN", rank=1011)
    level2 = classification_level_service.create_classification_level(admin, name="TEST_FREE", rank=1012)
    with pytest.raises(DuplicateClassificationLevelException):
        classification_level_service.update_classification_level(admin, level2.id, name="TEST_TAKEN")


# ---------------------------------------------------------------------------
# delete_classification_level
# ---------------------------------------------------------------------------

def test_delete_classification_level_removes_from_db(admin):
    level = classification_level_service.create_classification_level(admin, name="TEST_DELETE_ME", rank=1020)
    level_id = level.id
    classification_level_service.delete_classification_level(admin, level_id)
    assert not ClassificationLevel.objects.filter(id=level_id).exists()


def test_delete_classification_level_not_found_raises(admin):
    with pytest.raises(ClassificationLevelNotFoundException):
        classification_level_service.delete_classification_level(admin, 999999)

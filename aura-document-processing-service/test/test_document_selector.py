import pytest
from pydantic import ValidationError

from app.domain.dtos.document.bulk.document_selector import DocumentSelector


class TestDocumentSelector:
    def test_single_id(self):
        selector = DocumentSelector(document_ids=[5])
        assert selector.document_ids == [5]
        assert selector.all_documents is False

    def test_several_ids_are_deduplicated_preserving_order(self):
        selector = DocumentSelector(document_ids=[3, 1, 3, 2, 1])
        assert selector.document_ids == [3, 1, 2]

    def test_all_documents(self):
        selector = DocumentSelector(all_documents=True)
        assert selector.all_documents is True
        assert selector.document_ids is None

    def test_rejects_both_modes(self):
        with pytest.raises(ValidationError):
            DocumentSelector(document_ids=[1], all_documents=True)

    def test_rejects_neither_mode(self):
        with pytest.raises(ValidationError):
            DocumentSelector()

    def test_rejects_empty_id_list(self):
        with pytest.raises(ValidationError):
            DocumentSelector(document_ids=[])

    def test_rejects_out_of_range_id(self):
        with pytest.raises(ValidationError):
            DocumentSelector(document_ids=[0])

    def test_ignores_extra_fields(self):
        selector = DocumentSelector(all_documents=True, unexpected="x")
        assert selector.all_documents is True
        assert not hasattr(selector, "unexpected")

import pytest

from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


@pytest.fixture
def make_fragment():
    def _make(
            fragment_id: int = 1,
            content: str = "contenido",
            document_id: int = 10,
            document_name: str = "Documento de prueba",
            fragment_index: int = 0,
            page_number=None,
            section_path=None,
            heading=None,
    ) -> FragmentResponse:
        return FragmentResponse(
            id=fragment_id,
            content=content,
            fragment_index=fragment_index,
            page_number=page_number,
            section_path=section_path,
            heading=heading,
            document={"id": document_id, "name": document_name},
        )

    return _make

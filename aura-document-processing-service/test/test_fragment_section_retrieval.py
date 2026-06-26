from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.fragment.fragment_query_service.fragment_query_service import FragmentQueryService
from app.application.services.fragment.fragment_query_service.fragment_query_service_settings import (
    FragmentQueryServiceSettings,
)
from app.domain.dtos.fragment.fragment_query.fragment_response import FragmentResponse
from app.domain.dtos.fragment.fragment_query.question_context_fragments_request import (
    QuestionContextFragmentsRequest,
)


def _frag(fragment_id, *, document_id=1, fragment_index=0, section_path="Cap 1", content="c"):
    return SimpleNamespace(
        id=fragment_id,
        document_id=document_id,
        fragment_index=fragment_index,
        section_path=section_path,
        content=content,
    )


def _resp(fragment_id, *, document_id=1, fragment_index=0):
    return FragmentResponse(
        id=fragment_id,
        content="c",
        fragment_index=fragment_index,
        document={"id": document_id, "name": "Doc"},
    )



class TestSelectSectionMembers:
    def test_section_window_and_boundary(self):
        primary = _frag(1, fragment_index=10, section_path="A")
        pool = [
            _frag(2, fragment_index=11, section_path="A"),
            _frag(3, fragment_index=10, section_path="B"),
            _frag(4, fragment_index=100, section_path="A"),
            _frag(5, fragment_index=9, section_path="A"),
        ]
        members = FragmentQueryService._select_section_members(
            primary=primary, pool=pool, seen=set(), primary_ids={1}, half=3, fallback_window=1
        )
        assert [m.id for m in members] == [5, 2]

    def test_dedup_excludes_seen_and_primaries(self):
        primary = _frag(1, fragment_index=0, section_path="A")
        pool = [_frag(2, fragment_index=1, section_path="A"), _frag(9, fragment_index=1, section_path="A")]
        members = FragmentQueryService._select_section_members(
            primary=primary, pool=pool, seen={2}, primary_ids={1, 9}, half=3, fallback_window=1
        )
        assert members == []

    def test_fallback_window_for_no_section_primary(self):
        primary = _frag(1, fragment_index=5, section_path=None)
        pool = [
            _frag(2, fragment_index=6, section_path=None),
            _frag(3, fragment_index=8, section_path=None),
        ]
        members = FragmentQueryService._select_section_members(
            primary=primary, pool=pool, seen=set(), primary_ids={1}, half=6, fallback_window=1
        )
        assert [m.id for m in members] == [2]



def _make_service(**section_kwargs):
    settings = FragmentQueryServiceSettings(max_section_fragments=12, **section_kwargs)
    return FragmentQueryService(
        document_repository=AsyncMock(),
        fragment_repository=AsyncMock(),
        embedder_factory=MagicMock(),
        reranker_factory=MagicMock(),
        document_collection_catalog_client=AsyncMock(),
        chat_membership_provider=AsyncMock(),
        database_manager=AsyncMock(),
        fragment_query_service_settings=settings,
    )


def _request() -> QuestionContextFragmentsRequest:
    return QuestionContextFragmentsRequest(
        semantic_queries=[{"text": "q", "max_fragments": 5}],
        context_expansion="section",
    )


class TestBuildSectionResponse:
    async def test_groups_primaries_with_section_and_dedups(self, monkeypatch):
        service = _make_service()

        primaries = [_frag(1, fragment_index=0, section_path="A"), _frag(2, fragment_index=2, section_path="A")]
        pool = [_frag(11, fragment_index=1, section_path="A"), _frag(12, fragment_index=3, section_path="A")]

        service._fragment_repository.get_section_fragments = AsyncMock(return_value=pool)
        service._fragment_repository.get_adjacent_fragments = AsyncMock(return_value=[])

        async def _fake_map(fragments, database_session):
            return {f.id: _resp(f.id, fragment_index=f.fragment_index) for f in fragments}

        monkeypatch.setattr(service, "_build_fragment_response_map", _fake_map)

        response = await service._build_section_response(
            primaries=primaries,
            request=_request(),
            database_session=MagicMock(),
            accessible_doc_set={1},
        )

        assert [f.id for f in response.fragments] == [1, 2]
        assert response.groups is not None and len(response.groups) == 2
        assert [f.id for f in response.groups[0].section_fragments] == [11, 12]
        assert response.groups[1].section_fragments == []

    async def test_no_section_path_uses_adjacent_fallback(self, monkeypatch):
        service = _make_service()

        primaries = [_frag(1, fragment_index=5, section_path=None)]
        adjacent_pool = [_frag(7, fragment_index=6, section_path=None)]

        service._fragment_repository.get_section_fragments = AsyncMock(return_value=[])
        service._fragment_repository.get_adjacent_fragments = AsyncMock(return_value=adjacent_pool)

        async def _fake_map(fragments, database_session):
            return {f.id: _resp(f.id, fragment_index=f.fragment_index) for f in fragments}

        monkeypatch.setattr(service, "_build_fragment_response_map", _fake_map)

        response = await service._build_section_response(
            primaries=primaries,
            request=_request(),
            database_session=MagicMock(),
            accessible_doc_set={1},
        )

        service._fragment_repository.get_adjacent_fragments.assert_awaited_once()
        service._fragment_repository.get_section_fragments.assert_not_called()
        assert [f.id for f in response.groups[0].section_fragments] == [7]

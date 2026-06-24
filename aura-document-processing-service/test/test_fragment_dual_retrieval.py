from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.fragment.fragment_query_service.fragment_query_service import FragmentQueryService
from app.application.services.fragment.fragment_query_service.fragment_query_service_settings import (
    FragmentQueryServiceSettings,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.fragment.fragment_query.question_context_fragments_request import (
    QuestionContextFragmentsRequest,
)


def _user(user_id: int = 3) -> AuthenticatedUser:
    return AuthenticatedUser(id=user_id, email="u@test.com", roles=[], permissions=[])


def _frag(fragment_id, *, document_id=1, fragment_index=0, content="c", contextualized_content=None):
    return SimpleNamespace(
        id=fragment_id,
        document_id=document_id,
        fragment_index=fragment_index,
        content=content,
        contextualized_content=contextualized_content,
        page_number=None,
        section_path=None,
        heading=None,
        char_start=None,
        char_end=None,
        bbox=None,
    )


class _FakeDatabaseManager:
    @asynccontextmanager
    async def session(self):
        yield MagicMock(name="session")


def _make_service(*, contextual_enabled=True):
    settings = FragmentQueryServiceSettings(contextual_retrieval_enabled=contextual_enabled)
    embedder_factory = MagicMock()
    embedder_factory.embedder.aembed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
    embedder_factory.get_active_embedding_identity.return_value = "model:dim:instr"

    document_repository = AsyncMock()
    document_repository.get_documents_by_ids.return_value = [
        SimpleNamespace(id=1, name="Doc", description=None, type=None, category=None)
    ]

    catalog = AsyncMock()
    catalog.fetch_all_accessible_document_ids.return_value = [1]

    service = FragmentQueryService(
        document_repository=document_repository,
        fragment_repository=AsyncMock(),
        embedder_factory=embedder_factory,
        reranker_factory=MagicMock(),
        document_collection_catalog_client=catalog,
        chat_membership_provider=AsyncMock(),
        database_manager=_FakeDatabaseManager(),
        fragment_query_service_settings=settings,
    )
    return service


def _request() -> QuestionContextFragmentsRequest:
    return QuestionContextFragmentsRequest(
        semantic_queries=[{"text": "q", "max_fragments": 5}],
        context_expansion="none",
    )


class TestDualLaneRetrieval:
    async def test_runs_raw_and_contextual_lanes_and_fuses(self):
        service = _make_service(contextual_enabled=True)

        raw = [_frag(1, contextualized_content="ctx-1\n\nc"), _frag(2)]
        contextual = [_frag(1, contextualized_content="ctx-1\n\nc")]

        async def _similar(*, representation="raw", **kwargs):
            return contextual if representation == "contextual" else raw

        service._fragment_repository.get_most_similar_fragments = AsyncMock(side_effect=_similar)

        response = await service.retrieve_context_fragments_by_question(
            question_context_fragments_request=_request(),
            database_session=MagicMock(),
            authenticated_user=_user(),
            authorization_header="tok",
        )

        representations = [
            c.kwargs.get("representation", "raw")
            for c in service._fragment_repository.get_most_similar_fragments.call_args_list
        ]
        assert "raw" in representations and "contextual" in representations

        ids = [f.id for f in response.fragments]
        assert set(ids) == {1, 2}
        assert ids[0] == 1
        primary = next(f for f in response.fragments if f.id == 1)
        assert primary.contextualized_content == "ctx-1\n\nc"

    async def test_bm25_runs_raw_and_contextual_lanes(self):
        service = _make_service(contextual_enabled=True)

        service._fragment_repository.get_most_similar_fragments = AsyncMock(return_value=[_frag(1)])

        async def _bm25(*, representation="raw", **kwargs):
            return [_frag(2, contextualized_content="ctx-2\n\nc")] if representation == "contextual" else [_frag(1)]

        service._fragment_repository.get_most_relevant_fragments_bm25 = AsyncMock(side_effect=_bm25)

        request = QuestionContextFragmentsRequest(
            semantic_queries=[{"text": "q", "max_fragments": 5}],
            bm25_queries=[{"text": "kw", "max_fragments": 5}],
            context_expansion="none",
        )
        response = await service.retrieve_context_fragments_by_question(
            question_context_fragments_request=request,
            database_session=MagicMock(),
            authenticated_user=_user(),
            authorization_header="tok",
        )

        bm25_reprs = [
            c.kwargs.get("representation", "raw")
            for c in service._fragment_repository.get_most_relevant_fragments_bm25.call_args_list
        ]
        assert "raw" in bm25_reprs and "contextual" in bm25_reprs
        assert {f.id for f in response.fragments} == {1, 2}

    async def test_disabled_runs_only_raw_lane(self):
        service = _make_service(contextual_enabled=False)

        async def _similar(*, representation="raw", **kwargs):
            assert representation == "raw"
            return [_frag(1), _frag(2)]

        service._fragment_repository.get_most_similar_fragments = AsyncMock(side_effect=_similar)

        response = await service.retrieve_context_fragments_by_question(
            question_context_fragments_request=_request(),
            database_session=MagicMock(),
            authenticated_user=_user(),
            authorization_header="tok",
        )

        representations = [
            c.kwargs.get("representation", "raw")
            for c in service._fragment_repository.get_most_similar_fragments.call_args_list
        ]
        assert representations == ["raw"]
        assert {f.id for f in response.fragments} == {1, 2}

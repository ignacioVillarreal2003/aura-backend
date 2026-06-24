from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.document.document_search_service.document_search_service import (
    DocumentSearchService,
)
from app.application.services.document.document_search_service.document_search_service_settings import (
    DocumentSearchServiceSettings,
)
from app.domain.constants.document.document_search_mode import DocumentSearchMode
from app.domain.dtos.document.document_search.document_search_request import DocumentSearchRequest
from app.domain.dtos.document.document_search.document_similarity_hit import DocumentSimilarityHit


AUTH_HEADER = "Bearer test-token"


def _user(user_id: int = 42):
    return SimpleNamespace(id=user_id)


def _document(doc_id: int, name: str = "doc"):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=doc_id,
        chat_id=None,
        name=name,
        description=None,
        mime_type="pdf",
        status="processed",
        file_size_bytes=1234,
        type=None,
        category=None,
        enrichment_status="completed",
        graph_status="not_required",
        processing_started_at=now,
        processing_finished_at=now,
        created_by=42,
        created_at=now,
        updated_by=None,
        updated_at=None,
        deleted_by=None,
        deleted_at=None,
    )


def _hit(doc_id: int, score: float, matched: int = 1, content: str | None = "snippet"):
    return DocumentSimilarityHit(
        document_id=doc_id,
        score=score,
        matched_fragments=matched,
        best_fragment_content=content,
    )


def _fragment(doc_id: int, content: str, frag_id: int):
    return SimpleNamespace(id=frag_id, document_id=doc_id, content=content)


def _build_service(
    *,
    accessible_ids,
    vector_hits=None,
    bm25_hits=None,
    fragments=None,
    bm25_fragments=None,
    documents=None,
    settings: DocumentSearchServiceSettings | None = None,
    reranker=None,
):
    catalog = MagicMock()
    catalog.fetch_all_accessible_document_ids = AsyncMock(return_value=list(accessible_ids))

    fragment_repo = MagicMock()
    fragment_repo.search_documents_by_similarity = AsyncMock(return_value=list(vector_hits or []))
    fragment_repo.search_documents_by_bm25 = AsyncMock(return_value=list(bm25_hits or []))
    fragment_repo.get_most_similar_fragments = AsyncMock(return_value=list(fragments or []))
    fragment_repo.get_most_relevant_fragments_bm25 = AsyncMock(return_value=list(bm25_fragments or []))

    document_repo = MagicMock()
    document_repo.get_documents_by_ids = AsyncMock(return_value=list(documents or []))

    embedder_factory = MagicMock()
    embedder_factory.embedder = MagicMock()
    embedder_factory.embedder.aembed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
    embedder_factory.get_active_embedding_identity = MagicMock(return_value="model::1024")

    reranker_factory = None
    if reranker is not None:
        reranker_factory = MagicMock()
        reranker_factory.reranker = reranker

    if settings is None:
        settings = DocumentSearchServiceSettings(rerank_enabled=reranker is not None)

    service = DocumentSearchService(
        document_repository=document_repo,
        fragment_repository=fragment_repo,
        embedder_factory=embedder_factory,
        document_collection_catalog_client=catalog,
        reranker_factory=reranker_factory,
        document_search_service_settings=settings,
    )
    return service, fragment_repo, document_repo, embedder_factory


async def test_vector_mode_returns_cosine_similarity_and_metadata():
    docs = [_document(1, "alpha"), _document(2, "beta")]
    hits = [_hit(1, 0.83), _hit(2, 0.55)]
    service, fragment_repo, _, embedder_factory = _build_service(
        accessible_ids=[1, 2], vector_hits=hits, documents=docs
    )

    request = DocumentSearchRequest(query="riesgos", mode=DocumentSearchMode.vector, page=1, page_size=10)
    response = await service.search_documents_by_content(
        document_search_request=request,
        database_session=MagicMock(),
        authenticated_user=_user(),
        authorization_header=AUTH_HEADER,
    )

    assert response.mode is DocumentSearchMode.vector
    assert response.page == 1
    assert response.page_size == 10
    assert response.has_more is False
    assert [r.document.id for r in response.results] == [1, 2]
    assert response.results[0].similarity == pytest.approx(0.83)
    assert response.results[0].score == pytest.approx(0.83)
    fragment_repo.search_documents_by_similarity.assert_awaited_once()
    fragment_repo.search_documents_by_bm25.assert_not_awaited()
    embedder_factory.embedder.aembed_query.assert_awaited_once()


async def test_bm25_mode_normalizes_score_and_uses_lexical_repo():
    docs = [_document(7, "gamma")]
    hits = [_hit(7, 10.0)]
    settings = DocumentSearchServiceSettings(bm25_relevance_saturation=10.0)
    service, fragment_repo, _, embedder_factory = _build_service(
        accessible_ids=[7], bm25_hits=hits, documents=docs, settings=settings
    )

    request = DocumentSearchRequest(query="seguridad", mode=DocumentSearchMode.bm25, page=1, page_size=10)
    response = await service.search_documents_by_content(
        document_search_request=request,
        database_session=MagicMock(),
        authenticated_user=_user(),
        authorization_header=AUTH_HEADER,
    )

    assert response.mode is DocumentSearchMode.bm25
    assert response.results[0].score == pytest.approx(10.0)
    assert response.results[0].similarity == pytest.approx(0.5)
    fragment_repo.search_documents_by_bm25.assert_awaited_once()
    fragment_repo.search_documents_by_similarity.assert_not_awaited()
    embedder_factory.embedder.aembed_query.assert_not_awaited()


async def test_has_more_true_when_repo_returns_more_than_page_size():
    docs = [_document(i) for i in range(1, 4)]
    hits = [_hit(1, 0.9), _hit(2, 0.8), _hit(3, 0.7)]
    service, fragment_repo, document_repo, _ = _build_service(
        accessible_ids=[1, 2, 3], vector_hits=hits, documents=docs[:2]
    )

    request = DocumentSearchRequest(query="q", mode=DocumentSearchMode.vector, page=2, page_size=2)
    response = await service.search_documents_by_content(
        document_search_request=request,
        database_session=MagicMock(),
        authenticated_user=_user(),
        authorization_header=AUTH_HEADER,
    )

    assert response.has_more is True
    assert len(response.results) == 2
    _, kwargs = fragment_repo.search_documents_by_similarity.call_args
    assert kwargs["offset"] == 2
    assert kwargs["k"] == 3
    _, doc_kwargs = document_repo.get_documents_by_ids.call_args
    assert doc_kwargs["document_ids"] == [1, 2]


async def test_no_accessible_documents_returns_empty_with_echoed_metadata():
    service, fragment_repo, _, _ = _build_service(accessible_ids=[])

    request = DocumentSearchRequest(query="q", mode=DocumentSearchMode.bm25, page=3, page_size=5)
    response = await service.search_documents_by_content(
        document_search_request=request,
        database_session=MagicMock(),
        authenticated_user=_user(),
        authorization_header=AUTH_HEADER,
    )

    assert response.results == []
    assert response.has_more is False
    assert response.mode is DocumentSearchMode.bm25
    assert response.page == 3
    assert response.page_size == 5
    fragment_repo.search_documents_by_bm25.assert_not_awaited()
    fragment_repo.search_documents_by_similarity.assert_not_awaited()


async def test_hybrid_rerank_surfaces_bm25_only_match():
    docs = [_document(1, "uno"), _document(2, "dos"), _document(3, "tres")]
    vector_frags = [
        _fragment(1, "texto generico de uno", frag_id=10),
        _fragment(2, "texto generico de dos", frag_id=20),
    ]
    bm25_frags = [
        _fragment(3, "ausencia de las autoridades con competencia en su jurisdiccion", frag_id=30),
    ]
    reranker = MagicMock()
    reranker.rerank_with_scores = AsyncMock(return_value=[(2, 0.97), (0, 0.30), (1, 0.10)])

    service, fragment_repo, _, _ = _build_service(
        accessible_ids=[1, 2, 3],
        fragments=vector_frags,
        bm25_fragments=bm25_frags,
        documents=docs,
        reranker=reranker,
    )

    request = DocumentSearchRequest(query="ausencia de las autoridades", mode=DocumentSearchMode.vector, page=1, page_size=10)
    response = await service.search_documents_by_content(
        document_search_request=request,
        database_session=MagicMock(),
        authenticated_user=_user(),
        authorization_header=AUTH_HEADER,
    )

    assert [r.document.id for r in response.results] == [3, 1, 2]
    top = response.results[0]
    assert top.document.id == 3
    assert top.similarity == pytest.approx(0.97)
    assert top.best_fragment_snippet == "ausencia de las autoridades con competencia en su jurisdiccion"
    fragment_repo.get_most_similar_fragments.assert_awaited_once()
    fragment_repo.get_most_relevant_fragments_bm25.assert_awaited_once()
    reranker.rerank_with_scores.assert_awaited_once()


async def test_rerank_falls_back_to_vector_when_reranker_errors():
    docs = [_document(1), _document(2)]
    frags = [_fragment(1, "a", frag_id=1), _fragment(2, "b", frag_id=2)]
    hits = [_hit(1, 0.9), _hit(2, 0.7)]
    reranker = MagicMock()
    reranker.rerank_with_scores = AsyncMock(side_effect=RuntimeError("model down"))

    service, _, _, _ = _build_service(
        accessible_ids=[1, 2], fragments=frags, vector_hits=hits, documents=docs, reranker=reranker
    )

    request = DocumentSearchRequest(query="q", mode=DocumentSearchMode.vector, page=1, page_size=10)
    response = await service.search_documents_by_content(
        document_search_request=request,
        database_session=MagicMock(),
        authenticated_user=_user(),
        authorization_header=AUTH_HEADER,
    )

    assert [r.document.id for r in response.results] == [1, 2]
    assert response.results[0].similarity == pytest.approx(0.9)
    assert response.results[0].score == pytest.approx(0.9)


async def test_inaccessible_hits_are_filtered_out():
    docs = [_document(1)]
    hits = [_hit(1, 0.9), _hit(999, 0.95)]
    service, _, document_repo, _ = _build_service(
        accessible_ids=[1], vector_hits=hits, documents=docs
    )

    request = DocumentSearchRequest(query="q", mode=DocumentSearchMode.vector, page=1, page_size=10)
    response = await service.search_documents_by_content(
        document_search_request=request,
        database_session=MagicMock(),
        authenticated_user=_user(),
        authorization_header=AUTH_HEADER,
    )

    assert [r.document.id for r in response.results] == [1]

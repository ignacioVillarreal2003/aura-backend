import logging
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.fragment.fragment_query_service.interfaces.fragment_query_service_interface import (
    FragmentQueryServiceInterface,
)
from app.domain.dtos.fragment.fragment_query.fragment_list_response import FragmentListResponse
from app.application.services.graph.graph_query_service.interfaces.graph_query_service_interface import (
    GraphQueryServiceInterface,
)
from app.application.services.graph.hybrid_retrieval_orchestrator.interfaces.hybrid_retrieval_orchestrator_interface import (
    HybridRetrievalOrchestratorInterface,
)
from app.configuration.knowledge_graph_settings import KnowledgeGraphSettings
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.graph.query_intent import QueryIntent
from app.domain.dtos.fragment.fragment_query.question_context_fragments_request import (
    QuestionContextFragmentsRequest,
)
from app.domain.field_limits import MAX_FRAGMENTS_PER_QUERY_STRATEGY
from app.domain.dtos.graph.graph_query.graph_hybrid_query_response import (
    GraphHybridQueryResponse,
    HybridRetrievalSource,
)
from app.domain.dtos.graph.graph_query.graph_query_request import GraphQueryRequest
from app.domain.dtos.graph.graph_query.graph_query_response import GraphQueryResponse

logger = logging.getLogger(__name__)


class HybridRetrievalOrchestrator(HybridRetrievalOrchestratorInterface):
    """Composes the knowledge-graph and the legacy vector-search paths.

    Strategy (intentionally simple and explicit):

    1. Authorize the request and ensure the user has BOTH the KG query
       and the vector-search permissions; if they only have one, the
       orchestrator will degrade to a single-path response.
    2. Try the KG path first via ``GraphQueryService.execute``.
    3. Use the KG response when:
        - ``intent`` is one of FIND_ENTITY, FIND_NEIGHBORS, FIND_PATH,
          FILTER_BY_TYPE,
        - AND ``confidence >= hybrid_intent_confidence_threshold``,
        - AND the response carries at least
          ``hybrid_min_kg_results`` items (entities or relations).
    4. Otherwise fall back to ``FragmentQueryService.retrieve_context_fragments_by_question``.
    5. Return a unified response that exposes ONE primary source. We do
       NOT mix the two result sets in this version (out of scope per the
       plan); ranking-level hybridization is left for a future iteration.

    Important: ``FragmentQueryService`` is consumed via its existing
    interface. No code path here mutates RAG state.
    """

    def __init__(
            self,
            *,
            graph_query_service: GraphQueryServiceInterface,
            fragment_query_service: FragmentQueryServiceInterface,
            authorizer: Authorizer,
            knowledge_graph_settings: Optional[KnowledgeGraphSettings] = None,
    ) -> None:
        self._graph_query_service = graph_query_service
        self._fragment_query_service = fragment_query_service
        self._authorizer = authorizer
        self._settings = knowledge_graph_settings or KnowledgeGraphSettings()

    async def retrieve(
            self,
            *,
            request: GraphQueryRequest,
            authenticated_user: AuthenticatedUser,
            database_session: AsyncSession,
    ) -> GraphHybridQueryResponse:
        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.HYBRID_KNOWLEDGE_GRAPH_QUERY}),
        )

        kg_response: Optional[GraphQueryResponse]
        kg_response = await self._safe_kg_query(
            request=request,
            authenticated_user=authenticated_user,
            database_session=database_session,
        )

        if kg_response is not None and self._is_kg_response_acceptable(kg_response):
            logger.info(
                "Hybrid retrieval served the request from the knowledge graph.",
                extra={
                    "user_id": authenticated_user.id,
                    "intent": kg_response.intent.value,
                    "confidence": kg_response.confidence,
                    "entities_count": len(kg_response.entities),
                    "relations_count": len(kg_response.relations),
                },
            )
            return GraphHybridQueryResponse(
                source=HybridRetrievalSource.KNOWLEDGE_GRAPH,
                confidence=kg_response.confidence,
                fallback_used=False,
                kg_results=kg_response,
                rag_results=None,
            )

        rag_response = await self._safe_rag_query(
            request=request,
            authenticated_user=authenticated_user,
            database_session=database_session,
        )

        if rag_response is None:
            logger.info(
                "Hybrid retrieval found no results from KG or RAG.",
                extra={"user_id": authenticated_user.id},
            )
            return GraphHybridQueryResponse(
                source=HybridRetrievalSource.NONE,
                confidence=kg_response.confidence if kg_response else 0.0,
                fallback_used=True,
                kg_results=kg_response,
                rag_results=None,
            )

        logger.info(
            "Hybrid retrieval fell back to vector-search RAG.",
            extra={
                "user_id": authenticated_user.id,
                "kg_confidence": kg_response.confidence if kg_response else 0.0,
                "rag_fragments_count": len(rag_response.fragments),
            },
        )
        return GraphHybridQueryResponse(
            source=HybridRetrievalSource.VECTOR_SEARCH,
            confidence=kg_response.confidence if kg_response else 0.0,
            fallback_used=True,
            kg_results=kg_response,
            rag_results=rag_response,
        )

    async def _safe_kg_query(
            self,
            *,
            request: GraphQueryRequest,
            authenticated_user: AuthenticatedUser,
            database_session: AsyncSession,
    ) -> Optional[GraphQueryResponse]:
        try:
            return await self._graph_query_service.execute(
                request=request,
                authenticated_user=authenticated_user,
                database_session=database_session,
            )
        except Exception:
            logger.warning(
                "Knowledge graph query failed; the orchestrator will fall back to RAG.",
                extra={"user_id": authenticated_user.id},
                exc_info=True,
            )
            return None

    async def _safe_rag_query(
            self,
            *,
            request: GraphQueryRequest,
            authenticated_user: AuthenticatedUser,
            database_session: AsyncSession,
    ) -> Optional[FragmentListResponse]:
        try:
            rag_request = QuestionContextFragmentsRequest(
                chat_id=request.chat_id,
                semantic_queries=[
                    {"text": request.question, "max_fragments": min(request.max_results, MAX_FRAGMENTS_PER_QUERY_STRATEGY)},
                ],
            )
            return await self._fragment_query_service.retrieve_context_fragments_by_question(
                question_context_fragments_request=rag_request,
                database_session=database_session,
                authenticated_user=authenticated_user,
            )
        except Exception:
            logger.warning(
                "Vector-search RAG fallback failed in hybrid retrieval.",
                extra={"user_id": authenticated_user.id},
                exc_info=True,
            )
            return None

    def _is_kg_response_acceptable(self, kg_response: GraphQueryResponse) -> bool:
        if kg_response.intent == QueryIntent.UNKNOWN:
            return False
        if kg_response.confidence < self._settings.hybrid_intent_confidence_threshold:
            return False
        result_count = len(kg_response.entities) + len(kg_response.relations)
        if result_count < self._settings.hybrid_min_kg_results:
            return False
        return True


async def get_hybrid_retrieval_orchestrator(
        request: Request,
) -> HybridRetrievalOrchestratorInterface:
    orchestrator = getattr(request.app.state, "hybrid_retrieval_orchestrator", None)
    if orchestrator is None:
        logger.error("HybridRetrievalOrchestrator is not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hybrid knowledge graph orchestrator is not available.",
        )
    return orchestrator

import logging
from typing import Any, Dict, List

from app.application.services.user_interactions.agent_service.agent_settings import AgentServiceSettings
from app.application.services.user_interactions.agent_service.agent_state.agent_state import AgentState
from app.application.services.user_interactions.agent_service.interfaces.node_interface import NodeInterface
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)

logger = logging.getLogger(__name__)

_MAX_DOCUMENT_IDS = 3


class DocumentFetcherNode(NodeInterface):
    """
    Handles busqueda_documento intent by fetching full document content rather
    than relevance-based fragments. Strategy:
      1. Semantic + keyword search to discover the internal document IDs.
      2. Retrieve all fragments of those documents for a complete picture.
    """

    def __init__(
            self,
            document_context_provider: DocumentContextProviderInterface,
            settings: AgentServiceSettings,
    ) -> None:
        self._provider = document_context_provider
        self._settings = settings
        logger.debug("DocumentFetcherNode initialized")

    async def process(self, agent_state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing document fetcher")

        resolved_query = agent_state.get("resolved_query", "") or agent_state.get("normalized_query", "")
        keywords: List[str] = agent_state.get("keywords", [])
        authenticated_user: AuthenticatedUser = agent_state["authenticated_user"]

        if not resolved_query:
            logger.warning("No query for document fetcher")
            return {"retrieved_fragments": []}

        try:
            fragments = await self._fetch(authenticated_user, resolved_query, keywords)
            logger.info("Document fetch completed", extra={"fragments_count": len(fragments)})
            return {"retrieved_fragments": fragments}

        except Exception:
            logger.error("Document fetcher failed — returning empty fragment list", exc_info=True)
            return {"retrieved_fragments": []}

    async def _fetch(
            self,
            authenticated_user: AuthenticatedUser,
            query: str,
            keywords: List[str],
    ) -> List[FragmentResponse]:
        search_query = " ".join(keywords)[:16_000] if keywords else query

        discovery_response = await self._provider.retrieve_context_fragments_by_question(
            authenticated_user=authenticated_user,
            question=search_query,
            question_max_fragments=self._settings.max_vector_fragments,
            use_keywords=True,
            keywords=search_query[:16_000],
            keywords_max_fragments=self._settings.max_keyword_fragments,
            use_rerank=None,
            rerank_max_fragments=None,
        )

        if not discovery_response.fragments:
            return []

        seen: set = set()
        doc_ids: List[int] = []
        for f in discovery_response.fragments:
            if f.document_id not in seen:
                seen.add(f.document_id)
                doc_ids.append(f.document_id)
            if len(doc_ids) >= _MAX_DOCUMENT_IDS:
                break

        full_response = await self._provider.retrieve_context_fragments_by_document(
            authenticated_user=authenticated_user,
            document_ids=doc_ids,
        )
        return full_response.fragments

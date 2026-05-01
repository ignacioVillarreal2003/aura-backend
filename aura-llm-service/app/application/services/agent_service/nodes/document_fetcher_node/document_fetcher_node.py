import logging
from typing import Any, Dict, List, Optional

from app.application.services.agent_service.agent_settings import AgentServiceSettings
from app.application.services.agent_service.agent_state.agent_state import AgentState
from app.application.services.agent_service.interfaces.node_interface import NodeInterface
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
      1. Semantic search using entity names to discover the internal document IDs.
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
        entities: dict = agent_state.get("entities", {})
        keywords: List[str] = agent_state.get("keywords", [])
        authenticated_user: AuthenticatedUser = agent_state["authenticated_user"]

        if not resolved_query:
            logger.warning("No query for document fetcher")
            return {"retrieved_fragments": []}

        try:
            fragments = await self._fetch(authenticated_user, resolved_query, entities, keywords)
            logger.info("Document fetch completed", extra={"fragments_count": len(fragments)})
            return {"retrieved_fragments": fragments}

        except Exception:
            logger.error("Document fetcher failed — returning empty fragment list", exc_info=True)
            return {"retrieved_fragments": []}

    async def _fetch(
            self,
            authenticated_user: AuthenticatedUser,
            query: str,
            entities: dict,
            keywords: List[str],
    ) -> List[FragmentResponse]:
        # Step 1: build a focused search string from entity names (leyes are most precise)
        search_query = self._build_entity_query(entities, keywords, query)

        # Step 2: find relevant fragments → extract document IDs
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

        # Step 3: take the top distinct document IDs
        seen: set = set()
        doc_ids: List[int] = []
        for f in discovery_response.fragments:
            if f.document_id not in seen:
                seen.add(f.document_id)
                doc_ids.append(f.document_id)
            if len(doc_ids) >= _MAX_DOCUMENT_IDS:
                break

        # Step 4: fetch all fragments of those documents for complete content
        full_response = await self._provider.retrieve_context_fragments_by_document(
            authenticated_user=authenticated_user,
            document_ids=doc_ids,
        )
        return full_response.fragments

    @staticmethod
    def _build_entity_query(entities: dict, keywords: List[str], fallback: str) -> str:
        # Leyes and organismos are the most discriminative entity types
        priority_terms: List[str] = (
            entities.get("leyes", []) +
            entities.get("organismos", []) +
            entities.get("cargos", [])
        )
        all_terms = priority_terms or keywords
        return " ".join(all_terms)[:16_000] if all_terms else fallback

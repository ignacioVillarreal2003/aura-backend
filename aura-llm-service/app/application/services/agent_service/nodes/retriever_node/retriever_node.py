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


class RetrieverNode(NodeInterface):
    def __init__(
            self,
            document_context_provider: DocumentContextProviderInterface,
            settings: AgentServiceSettings,
    ) -> None:
        self._provider = document_context_provider
        self._settings = settings
        logger.debug("RetrieverNode initialized")

    async def process(self, agent_state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing retriever")

        resolved_query = agent_state.get("resolved_query", "") or agent_state.get("normalized_query", "")
        keywords: List[str] = agent_state.get("keywords", [])
        entities: dict = agent_state.get("entities", {})
        authenticated_user: AuthenticatedUser = agent_state["authenticated_user"]

        if not resolved_query:
            logger.warning("No query available for retrieval")
            return {"retrieved_fragments": []}

        try:
            fragments = await self._retrieve(authenticated_user, resolved_query, keywords, entities)
            logger.info("Retrieval completed", extra={"fragments_count": len(fragments)})
            return {"retrieved_fragments": fragments}

        except Exception:
            logger.error("Retrieval failed — returning empty fragment list", exc_info=True)
            return {"retrieved_fragments": []}

    async def _retrieve(
            self,
            authenticated_user: AuthenticatedUser,
            query: str,
            keywords: List[str],
            entities: dict,
    ) -> List[FragmentResponse]:
        keywords_str = self._build_keywords_string(keywords, entities)
        use_keywords = bool(keywords_str)

        response = await self._provider.retrieve_context_fragments_by_question(
            authenticated_user=authenticated_user,
            question=query,
            question_max_fragments=self._settings.max_vector_fragments,
            use_keywords=use_keywords if use_keywords else None,
            keywords=keywords_str if use_keywords else None,
            keywords_max_fragments=self._settings.max_keyword_fragments if use_keywords else None,
            use_rerank=None,
            rerank_max_fragments=None,
        )
        return response.fragments

    @staticmethod
    def _build_keywords_string(keywords: List[str], entities: dict) -> Optional[str]:
        # Entity terms first (higher precision), then generic keywords
        entity_terms: List[str] = (
            entities.get("leyes", []) +
            entities.get("organismos", []) +
            entities.get("cargos", []) +
            entities.get("fechas", [])
        )
        all_terms = entity_terms + keywords
        if not all_terms:
            return None
        joined = " ".join(all_terms)
        return joined[:16_000] if joined else None

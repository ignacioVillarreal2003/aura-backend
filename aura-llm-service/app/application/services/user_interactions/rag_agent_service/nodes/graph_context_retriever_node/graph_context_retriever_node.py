import logging
from typing import Any, Dict, List, Optional

from app.application.services.user_interactions.rag_agent_service.interfaces.rag_node_interface import RagNodeInterface
from app.application.services.user_interactions.rag_agent_service.rag_agent_settings import RagAgentServiceSettings
from app.application.services.user_interactions.rag_agent_service.rag_agent_state.rag_agent_state import RagAgentState
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.graph_context_provider.interfaces.graph_context_provider_interface import (
    GraphContextProviderInterface,
)

logger = logging.getLogger(__name__)


class GraphContextRetrieverNode(RagNodeInterface):
    def __init__(
            self,
            graph_context_provider: Optional[GraphContextProviderInterface],
            settings: RagAgentServiceSettings,
    ) -> None:
        self._provider = graph_context_provider
        self._settings = settings
        logger.debug("GraphContextRetrieverNode initialized")

    async def process(self, state: RagAgentState) -> Dict[str, Any]:
        if (
                self._provider is None
                or not self._provider.is_active
                or not self._settings.use_graph_context
        ):
            return {"graph_facts": ""}

        query: str = state.get("query", "")
        keywords: List[str] = state.get("keywords", [])
        if not query and not keywords:
            return {"graph_facts": ""}

        authenticated_user: AuthenticatedUser = state["authenticated_user"]

        result = await self._provider.retrieve_graph_context(
            authenticated_user=authenticated_user,
            question=query or None,
            terms=keywords[: self._settings.graph_max_terms],
            chat_id=state.get("chat_id"),
            max_entities=self._settings.graph_max_entities,
            max_relations=self._settings.graph_max_relations,
        )

        if result.context_text:
            logger.info(
                "Graph facts added to the RAG context.",
                extra={
                    "facts_count": len(result.facts),
                    "context_chars": len(result.context_text),
                },
            )
        return {"graph_facts": result.context_text}

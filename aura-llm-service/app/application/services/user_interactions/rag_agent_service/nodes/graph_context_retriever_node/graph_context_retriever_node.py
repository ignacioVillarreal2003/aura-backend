import logging
from typing import Any, Dict, List, Optional

from app.application.services.user_interactions.rag_agent_service.constants.rag_query_intent import RagQueryIntent
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
        if self._provider is None or not self._provider.is_active:
            return {"graph_facts": ""}

        query: str = state.get("query", "")
        keywords: List[str] = state.get("keywords", [])
        if not query and not keywords:
            return {"graph_facts": ""}

        authenticated_user: AuthenticatedUser = state["authenticated_user"]
        intent: str = state.get("intent", RagQueryIntent.question.value)

        parts: List[str] = []

        if self._settings.use_graph_context:
            result = await self._provider.retrieve_graph_context(
                authenticated_user=authenticated_user,
                question=query or None,
                terms=keywords[: self._settings.graph_max_terms],
                chat_id=state.get("chat_id"),
                max_entities=self._settings.graph_max_entities,
                max_relations=self._settings.graph_max_relations,
            )
            if result.context_text:
                parts.append(result.context_text)
                logger.info(
                    "Graph facts added to the RAG context.",
                    extra={
                        "facts_count": len(result.facts),
                        "context_chars": len(result.context_text),
                    },
                )

        if (
                self._settings.use_graph_structured_query
                and intent == RagQueryIntent.relational.value
                and query
        ):
            structured = await self._provider.execute_graph_query(
                authenticated_user=authenticated_user,
                question=query,
                max_results=self._settings.graph_query_max_results,
                chat_id=state.get("chat_id"),
            )
            if structured.context_text:
                parts.append(structured.context_text)
                logger.info(
                    "Structured graph facts added to the RAG context.",
                    extra={
                        "entities_count": structured.entities_count,
                        "relations_count": structured.relations_count,
                        "context_chars": len(structured.context_text),
                    },
                )

        return {"graph_facts": "\n".join(parts)}

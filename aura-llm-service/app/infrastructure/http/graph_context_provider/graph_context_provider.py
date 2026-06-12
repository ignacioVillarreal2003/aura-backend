import logging
from typing import Optional

from app.configuration.tracing import retrieval_span, set_span_output
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.request_token import get_request_token
from app.infrastructure.http.graph_context_provider.dtos.graph_context_dtos import (
    GraphContextProviderRequest,
    GraphContextResult,
)
from app.infrastructure.http.graph_context_provider.graph_context_provider_settings import (
    GraphContextProviderSettings,
)
from app.infrastructure.http.graph_context_provider.interfaces.graph_context_provider_interface import (
    GraphContextProviderInterface,
)
from app.infrastructure.http.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)


class GraphContextProvider(GraphContextProviderInterface):
    def __init__(
            self,
            http_client: HttpClientInterface,
            graph_context_provider_settings: Optional[GraphContextProviderSettings] = None,
    ) -> None:
        self._http_client = http_client
        self._settings = graph_context_provider_settings or GraphContextProviderSettings()
        if not self._settings.is_active:
            logger.info(
                "GraphContextProvider is inactive (disabled or no URL configured); "
                "RAG graph enrichment will be skipped."
            )

    @property
    def is_active(self) -> bool:
        return self._settings.is_active

    async def retrieve_graph_context(
            self,
            *,
            authenticated_user: AuthenticatedUser,
            question: Optional[str],
            terms: list[str],
            chat_id: Optional[int] = None,
            max_entities: int = 8,
            max_relations: int = 30,
    ) -> GraphContextResult:
        if not self.is_active:
            return GraphContextResult.empty()
        if not terms and not (question and question.strip()):
            return GraphContextResult.empty()

        request_body = GraphContextProviderRequest(
            question=question,
            terms=terms,
            chat_id=chat_id,
            max_entities=max_entities,
            max_relations=max_relations,
        )

        try:
            with retrieval_span(
                    "retrieve_graph_context",
                    [question or "", *terms],
            ) as span:
                response = await self._http_client.post(
                    url=self._settings.url,
                    json=request_body.model_dump(exclude_none=True, mode="json"),
                    headers=self._build_headers(authenticated_user),
                    timeout=self._settings.timeout_seconds,
                )
                result = GraphContextResult.model_validate(response.json())
                set_span_output(span, result.context_text)
            logger.info(
                "Graph context retrieved for RAG.",
                extra={
                    "user_id": authenticated_user.id,
                    "facts_count": len(result.facts),
                    "context_chars": len(result.context_text),
                    "matched_terms": len(result.matched_terms),
                },
            )
            return result
        except Exception:
            logger.warning(
                "Graph context retrieval failed; continuing without graph facts.",
                extra={"user_id": authenticated_user.id},
                exc_info=True,
            )
            return GraphContextResult.empty()

    def _build_headers(
            self,
            authenticated_user: AuthenticatedUser,
    ) -> dict[str, str]:
        token = get_request_token()
        if not token:
            logger.warning(
                "No JWT available for outbound request; the downstream service will reject it.",
                extra={"user_id": authenticated_user.id},
            )
            return {}
        return {"Authorization": token}

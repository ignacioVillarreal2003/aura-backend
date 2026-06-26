import logging
from typing import Optional

from app.configuration.tracing import retrieval_span, set_span_output
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.request_token import get_request_token
from app.infrastructure.http.graph_context_provider.dtos.graph_context_dtos import (
    GraphContextProviderRequest,
    GraphContextResult,
    GraphQueryProviderRequest,
    GraphQueryProviderResponse,
    GraphQueryResult,
)
from app.infrastructure.http.graph_context_provider.graph_context_provider_settings import (
    GraphContextProviderSettings,
)
from app.infrastructure.http.graph_context_provider.interfaces.graph_context_provider_interface import (
    GraphContextProviderInterface,
)
from app.infrastructure.http.http_client.http_request_retry import retry_idempotent_request
from app.infrastructure.http.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)

_GRAPH_QUERY_CONTEXT_MAX_CHARS = 4_000


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
                payload = request_body.model_dump(exclude_none=True, mode="json")
                headers = self._build_headers(authenticated_user)
                response = await retry_idempotent_request(
                    lambda: self._http_client.post(
                        url=self._settings.url,
                        json=payload,
                        headers=headers,
                        timeout=self._settings.timeout_seconds,
                    ),
                    max_attempts=self._settings.retry_max_attempts,
                    min_wait=self._settings.retry_backoff_min_seconds,
                    max_wait=self._settings.retry_backoff_max_seconds,
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

    async def execute_graph_query(
            self,
            *,
            authenticated_user: AuthenticatedUser,
            question: str,
            max_results: int = 20,
            chat_id: Optional[int] = None,
    ) -> GraphQueryResult:
        query_url = self._settings.resolve_query_url
        if not self.is_active or not query_url:
            return GraphQueryResult.empty()
        if not question or not question.strip():
            return GraphQueryResult.empty()

        request_body = GraphQueryProviderRequest(
            question=question,
            max_results=max_results,
            chat_id=chat_id,
        )

        try:
            with retrieval_span("execute_graph_query", [question]) as span:
                payload = request_body.model_dump(exclude_none=True, mode="json")
                headers = self._build_headers(authenticated_user)
                response = await retry_idempotent_request(
                    lambda: self._http_client.post(
                        url=query_url,
                        json=payload,
                        headers=headers,
                        timeout=self._settings.timeout_seconds,
                    ),
                    max_attempts=self._settings.retry_max_attempts,
                    min_wait=self._settings.retry_backoff_min_seconds,
                    max_wait=self._settings.retry_backoff_max_seconds,
                )
                parsed = GraphQueryProviderResponse.model_validate(response.json())
                context_text = self._render_query_facts(parsed)
                set_span_output(span, context_text)
            result = GraphQueryResult(
                context_text=context_text,
                entities_count=len(parsed.entities),
                relations_count=len(parsed.relations),
            )
            logger.info(
                "Structured graph query executed for RAG.",
                extra={
                    "user_id": authenticated_user.id,
                    "entities_count": result.entities_count,
                    "relations_count": result.relations_count,
                    "context_chars": len(context_text),
                },
            )
            return result
        except Exception:
            logger.warning(
                "Structured graph query failed; continuing without structured graph facts.",
                extra={"user_id": authenticated_user.id},
                exc_info=True,
            )
            return GraphQueryResult.empty()

    @staticmethod
    def _render_query_facts(parsed: GraphQueryProviderResponse) -> str:
        lines: list[str] = []
        total = 0
        budget = _GRAPH_QUERY_CONTEXT_MAX_CHARS

        def append(text: str) -> bool:
            nonlocal total
            line = f"- {text}"
            if total + len(line) + 1 > budget:
                return False
            lines.append(line)
            total += len(line) + 1
            return True

        for entity in parsed.entities:
            if not entity.description:
                continue
            if not append(f"{entity.display_name} ({entity.type}): {entity.description}"):
                break

        for relation in parsed.relations:
            relation_label = relation.type.replace("_", " ")
            if not append(
                    f"{relation.source.display_name} —[{relation_label}]→ "
                    f"{relation.target.display_name}"
            ):
                break

        return "\n".join(lines)

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

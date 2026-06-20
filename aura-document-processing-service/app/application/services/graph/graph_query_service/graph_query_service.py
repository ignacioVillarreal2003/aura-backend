import logging
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.graph.graph_query_service.interfaces.graph_query_service_interface import (
    GraphQueryServiceInterface,
)
from app.application.services.graph.knowledge_graph_settings import KnowledgeGraphSettings
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.graph.entity_type import EntityType
from app.domain.constants.graph.query_intent import QueryIntent
from app.domain.constants.graph.relation_type import (
    DEFAULT_ALLOWED_RELATION_TYPES,
    normalize_relation_type,
)
from app.domain.dtos.graph.graph_entity.graph_entity_response import GraphEntityResponse
from app.domain.dtos.graph.graph_entity.graph_relation_response import GraphRelationResponse
from app.domain.dtos.graph.graph_query.graph_query_interpreted_as import GraphQueryInterpretedAs
from app.domain.dtos.graph.graph_query.graph_query_request import GraphQueryRequest
from app.domain.dtos.graph.graph_query.graph_query_response import GraphQueryResponse
from app.infrastructure.http.authentication_provider.request_token import get_request_token
from app.infrastructure.http.llm_provider.dtos.translate_graph_query_request import GraphOntology
from app.infrastructure.http.llm_provider.interfaces.llm_provider_interface import LlmProviderInterface
from app.infrastructure.http.document_collection_catalog.interfaces.document_collection_catalog_client_interface import (
    DocumentCollectionCatalogClientInterface,
)
from app.infrastructure.persistence.graph.repositories.interfaces.graph_entity_repository_interface import (
    GraphEntityRepositoryInterface,
)
from app.infrastructure.persistence.graph.repositories.interfaces.graph_path_repository_interface import (
    GraphPathRepositoryInterface,
)
from app.infrastructure.persistence.graph.repositories.interfaces.graph_relation_repository_interface import (
    GraphRelationRepositoryInterface,
)

logger = logging.getLogger(__name__)


class GraphQueryService(GraphQueryServiceInterface):
    def __init__(
            self,
            *,
            llm_provider: LlmProviderInterface,
            entity_repository: GraphEntityRepositoryInterface,
            relation_repository: GraphRelationRepositoryInterface,
            path_repository: Optional[GraphPathRepositoryInterface] = None,
            document_collection_catalog_client: DocumentCollectionCatalogClientInterface,
            knowledge_graph_settings: Optional[KnowledgeGraphSettings] = None,
    ) -> None:
        self._llm_provider = llm_provider
        self._entity_repository = entity_repository
        self._relation_repository = relation_repository
        self._path_repository = path_repository
        self._document_collection_catalog_client = document_collection_catalog_client
        self._settings = knowledge_graph_settings or KnowledgeGraphSettings()

    async def execute(
            self,
            *,
            request: GraphQueryRequest,
            authenticated_user: AuthenticatedUser,
            database_session: AsyncSession,
            authorization_header: str | None = None,
    ) -> GraphQueryResponse:
        accessible_ids = await self._resolve_accessible_ids(
            user_id=int(authenticated_user.id),
            authorization_header=authorization_header,
        )
        if not accessible_ids:
            logger.info(
                "Knowledge graph query returned no results because the user has no accessible documents.",
                extra={"user_id": authenticated_user.id},
            )
            return GraphQueryResponse(
                intent=QueryIntent.UNKNOWN,
                confidence=0.0,
                entities=[],
                relations=[],
                explanation="The user has no accessible documents.",
            )

        ontology = GraphOntology(
            entity_types=self._settings.resolve_allowed_entity_types(),
            relation_types=self._settings.resolve_allowed_relation_types()
                           or list(DEFAULT_ALLOWED_RELATION_TYPES),
        )

        translation = await self._llm_provider.translate_graph_query(
            question=request.question,
            ontology=ontology,
            authenticated_user=authenticated_user,
        )

        max_results = self._clamp_results(request.max_results)
        intent = translation.intent
        params = self._merge_llm_parameter_aliases(
            intent, translation.parameters or {}
        )

        try:
            entities, relations = await self._dispatch_intent(
                intent=intent,
                params=params,
                accessible_ids=accessible_ids,
                max_results=max_results,
            )
        except _GraphIntentParameterError as e:
            logger.info(
                "The LLM-emitted parameters did not match the intent schema.",
                extra={
                    "user_id": authenticated_user.id,
                    "intent": intent.value,
                    "reason": str(e),
                },
            )
            fallback_entities = await self._fulltext_fallback(
                question=request.question,
                accessible_ids=accessible_ids,
                max_results=max_results,
            )
            return GraphQueryResponse(
                intent=QueryIntent.UNKNOWN,
                confidence=translation.confidence,
                entities=fallback_entities,
                relations=[],
                nodes=self._build_nodes(fallback_entities, []),
                explanation=(
                    "The structured intent could not be executed; results come from "
                    "a fulltext entity search over the question."
                    if fallback_entities
                    else "The query could not be answered with the structured intent."
                ),
            )

        if not entities and not relations:
            fallback_entities = await self._fulltext_fallback(
                question=request.question,
                accessible_ids=accessible_ids,
                max_results=max_results,
            )
            if fallback_entities:
                entities = fallback_entities

        nodes = self._build_nodes(entities, relations)
        has_more = (len(entities) + len(relations)) >= max_results
        interpreted_as = self._build_interpreted_as(intent, params)

        return GraphQueryResponse(
            intent=intent,
            confidence=translation.confidence,
            entities=entities,
            relations=relations,
            nodes=nodes,
            explanation=translation.reasoning,
            interpreted_as=interpreted_as,
            has_more=has_more,
        )

    async def _fulltext_fallback(
            self,
            *,
            question: str,
            accessible_ids: list[int],
            max_results: int,
    ) -> list[GraphEntityResponse]:
        try:
            return await self._entity_repository.fulltext_search(
                query_string=question,
                entity_type=None,
                accessible_document_ids=accessible_ids,
                limit=max_results,
            )
        except Exception:
            logger.warning(
                "Fulltext fallback for the graph query failed (non-fatal).",
                exc_info=True,
            )
            return []

    @staticmethod
    def _merge_llm_parameter_aliases(
            intent: QueryIntent,
            params: dict[str, Any],
    ) -> dict[str, Any]:
        merged: dict[str, Any] = dict(params)

        def copy_alias_if_blank(dst: str, src: str) -> None:
            if merged.get(dst) is None or not str(merged.get(dst)).strip():
                raw = merged.get(src)
                if raw is not None and str(raw).strip():
                    merged[dst] = raw

        if intent in (QueryIntent.FIND_ENTITY, QueryIntent.FIND_NEIGHBORS):
            copy_alias_if_blank("entity_name", "name")
            copy_alias_if_blank("entity_type", "type")
        elif intent == QueryIntent.FILTER_BY_TYPE:
            copy_alias_if_blank("entity_type", "type")
        elif intent == QueryIntent.FIND_PATH:
            copy_alias_if_blank("source_name", "source")
            if merged.get("source_type") is None or not str(merged.get("source_type")).strip():
                alias = merged.get("source_entity_type") or merged.get("from_type")
                if alias is not None and str(alias).strip():
                    merged["source_type"] = alias
        elif intent == QueryIntent.LIST_BY_DOCUMENT:
            copy_alias_if_blank("document_id", "doc_id")
        return merged

    async def _dispatch_intent(
            self,
            *,
            intent: QueryIntent,
            params: dict[str, Any],
            accessible_ids: list[int],
            max_results: int,
    ) -> tuple[list[GraphEntityResponse], list[GraphRelationResponse]]:
        if intent == QueryIntent.FIND_ENTITY:
            return await self._handle_find_entity(params, accessible_ids, max_results)
        if intent == QueryIntent.FIND_NEIGHBORS:
            return await self._handle_find_neighbors(params, accessible_ids, max_results)
        if intent == QueryIntent.FIND_PATH:
            return await self._handle_find_path(params, accessible_ids, max_results)
        if intent == QueryIntent.FILTER_BY_TYPE:
            return await self._handle_filter_by_type(params, accessible_ids, max_results)
        if intent == QueryIntent.LIST_BY_DOCUMENT:
            return await self._handle_list_by_document(params, accessible_ids, max_results)
        return [], []

    async def _handle_find_entity(
            self,
            params: dict[str, Any],
            accessible_ids: list[int],
            max_results: int,
    ) -> tuple[list[GraphEntityResponse], list[GraphRelationResponse]]:
        canonical = self._read_canonical_name(params, "entity_name")
        entity_type = self._read_optional_entity_type(params, "entity_type")
        results = await self._entity_repository.search_by_name_prefix(
            canonical_prefix=canonical,
            entity_type=entity_type,
            accessible_document_ids=accessible_ids,
            limit=max_results,
        )
        if not results:
            results = await self._entity_repository.fulltext_search(
                query_string=canonical,
                entity_type=entity_type,
                accessible_document_ids=accessible_ids,
                limit=max_results,
            )
        return results, []

    async def _handle_find_neighbors(
            self,
            params: dict[str, Any],
            accessible_ids: list[int],
            max_results: int,
    ) -> tuple[list[GraphEntityResponse], list[GraphRelationResponse]]:
        canonical = self._read_canonical_name(params, "entity_name")
        entity_type = self._read_optional_entity_type(params, "entity_type")
        depth = self._read_int(
            params,
            "depth",
            default=self._settings.query_default_neighbor_depth,
            min_value=1,
            max_value=self._settings.query_max_neighbor_depth,
        )
        relation_filter = self._read_optional_relation_types(params, "relation_types")
        relations = await self._relation_repository.list_neighbors_of(
            canonical_name=canonical,
            entity_type=entity_type,
            depth=depth,
            relation_types=relation_filter,
            accessible_document_ids=accessible_ids,
            limit=max_results,
        )
        return [], relations

    async def _handle_find_path(
            self,
            params: dict[str, Any],
            accessible_ids: list[int],
            max_results: int,
    ) -> tuple[list[GraphEntityResponse], list[GraphRelationResponse]]:
        source_canonical = self._read_canonical_name(params, "source_name")
        source_type = self._read_optional_entity_type(params, "source_type")
        target_raw = params.get("target_name")
        target_canonical = (
            " ".join(str(target_raw).strip().lower().split())
            if target_raw and str(target_raw).strip()
            else None
        )
        target_type = self._read_optional_entity_type(params, "target_type")
        max_hops = self._read_int(
            params,
            "max_hops",
            default=self._settings.query_default_neighbor_depth,
            min_value=1,
            max_value=self._settings.query_max_neighbor_depth,
        )

        if target_canonical and self._path_repository is not None:
            try:
                paths = await self._path_repository.find_paths(
                    source_canonical_name=source_canonical,
                    source_type=source_type,
                    target_canonical_name=target_canonical,
                    target_type=target_type,
                    max_hops=max_hops,
                    max_paths=min(max_results, 10),
                    only_shortest=True,
                    accessible_document_ids=accessible_ids,
                )
                if paths:
                    path_nodes: list[GraphEntityResponse] = []
                    path_rels: list[GraphRelationResponse] = []
                    seen_nodes: set[tuple[str, str]] = set()
                    seen_rels: set[tuple[str, str, str]] = set()
                    for path in paths:
                        for node in path.nodes:
                            node_key = (node.canonical_name, node.type.value)
                            if node_key not in seen_nodes:
                                seen_nodes.add(node_key)
                                path_nodes.append(node)
                        for rel in path.relations:
                            rel_key = (rel.source.canonical_name, rel.target.canonical_name, rel.type)
                            if rel_key not in seen_rels:
                                seen_rels.add(rel_key)
                                path_rels.append(rel)
                    return path_nodes, path_rels
            except Exception:
                logger.warning(
                    "Real path finding failed for find_path NL intent; falling back to source neighbors.",
                    extra={"source": source_canonical, "target": target_canonical},
                )

        relations = await self._relation_repository.list_neighbors_of(
            canonical_name=source_canonical,
            entity_type=source_type,
            depth=max_hops,
            relation_types=None,
            accessible_document_ids=accessible_ids,
            limit=max_results,
        )
        return [], relations

    async def _handle_filter_by_type(
            self,
            params: dict[str, Any],
            accessible_ids: list[int],
            max_results: int,
    ) -> tuple[list[GraphEntityResponse], list[GraphRelationResponse]]:
        entity_type = self._read_required_entity_type(params, "entity_type")
        results = await self._entity_repository.list_by_type(
            entity_type=entity_type,
            accessible_document_ids=accessible_ids,
            limit=max_results,
        )
        return results, []

    async def _handle_list_by_document(
            self,
            params: dict[str, Any],
            accessible_ids: list[int],
            max_results: int,
    ) -> tuple[list[GraphEntityResponse], list[GraphRelationResponse]]:
        raw: Any = params.get("document_id")
        try:
            document_id = int(raw)
            if document_id <= 0:
                raise ValueError("document_id must be positive")
        except (TypeError, ValueError) as exc:
            raise _GraphIntentParameterError(
                "Missing or invalid 'document_id' parameter."
            ) from exc

        entities = await self._entity_repository.list_by_document(
            document_id=document_id,
            entity_type=None,
            accessible_document_ids=accessible_ids,
            limit=max_results,
        )
        relations = await self._relation_repository.list_by_document(
            document_id=document_id,
            accessible_document_ids=accessible_ids,
            limit=max_results,
        )
        return entities, relations

    @staticmethod
    def _build_nodes(
            entities: list[GraphEntityResponse],
            relations: list[GraphRelationResponse],
    ) -> list[GraphEntityResponse]:
        seen: dict[tuple[str, str], GraphEntityResponse] = {}

        for entity in entities:
            key = (entity.canonical_name, entity.type.value)
            if key not in seen:
                seen[key] = entity

        for rel in relations:
            for endpoint in (rel.source, rel.target):
                key = (endpoint.canonical_name, endpoint.type.value)
                if key not in seen:
                    seen[key] = GraphEntityResponse(
                        canonical_name=endpoint.canonical_name,
                        display_name=endpoint.display_name,
                        type=endpoint.type,
                    )

        return list(seen.values())

    @staticmethod
    def _build_interpreted_as(
            intent: QueryIntent,
            params: dict[str, Any],
    ) -> Optional[GraphQueryInterpretedAs]:
        if intent == QueryIntent.UNKNOWN:
            return None

        def _str_or_none(key: str) -> Optional[str]:
            v = params.get(key)
            return str(v).strip() or None if v is not None else None

        def _int_or_none(key: str) -> Optional[int]:
            v = params.get(key)
            try:
                return int(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        def _list_or_none(key: str) -> Optional[list[str]]:
            v = params.get(key)
            if not isinstance(v, list):
                return None
            cleaned = [str(i).strip() for i in v if i and str(i).strip()]
            return cleaned or None

        return GraphQueryInterpretedAs(
            intent=intent,
            entity_name=_str_or_none("entity_name"),
            entity_type=_str_or_none("entity_type"),
            source_name=_str_or_none("source_name"),
            target_name=_str_or_none("target_name"),
            depth=_int_or_none("depth"),
            relation_types=_list_or_none("relation_types"),
            document_id=_int_or_none("document_id"),
        )

    async def _resolve_accessible_ids(
            self,
            *,
            user_id: int,
            authorization_header: str | None,
    ) -> list[int]:
        token = authorization_header or get_request_token()
        accessible = await self._document_collection_catalog_client.fetch_all_accessible_document_ids(
            user_id=user_id,
            authorization_header=token,
        )
        return list(accessible)

    def _clamp_results(self, value: int) -> int:
        return max(1, min(int(value), self._settings.query_max_results))

    @staticmethod
    def _read_canonical_name(params: dict[str, Any], key: str) -> str:
        raw = params.get(key)
        if raw is None or not str(raw).strip():
            raise _GraphIntentParameterError(f"Missing required parameter '{key}'.")
        return " ".join(str(raw).strip().lower().split())

    @staticmethod
    def _read_optional_entity_type(
            params: dict[str, Any],
            key: str,
    ) -> Optional[EntityType]:
        raw = params.get(key)
        if raw is None or not str(raw).strip():
            return None
        return EntityType.parse(str(raw))

    @staticmethod
    def _read_required_entity_type(
            params: dict[str, Any],
            key: str,
    ) -> EntityType:
        raw = params.get(key)
        if raw is None or not str(raw).strip():
            raise _GraphIntentParameterError(f"Missing required parameter '{key}'.")
        return EntityType.parse(str(raw))

    @staticmethod
    def _read_optional_relation_types(
            params: dict[str, Any],
            key: str,
    ) -> Optional[list[str]]:
        raw = params.get(key)
        if raw is None:
            return None
        if not isinstance(raw, list):
            return None
        normalized = [normalize_relation_type(str(item)) for item in raw if item]
        return normalized or None

    @staticmethod
    def _read_int(
            params: dict[str, Any],
            key: str,
            *,
            default: int,
            min_value: int,
            max_value: int,
    ) -> int:
        raw = params.get(key, default)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = default
        return max(min_value, min(value, max_value))


class _GraphIntentParameterError(Exception):
    pass

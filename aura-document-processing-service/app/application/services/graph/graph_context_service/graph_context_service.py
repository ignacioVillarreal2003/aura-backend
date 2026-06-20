import asyncio
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.graph.graph_context_service.interfaces.graph_context_service_interface import (
    GraphContextServiceInterface,
)
from app.application.services.graph.knowledge_graph_settings import KnowledgeGraphSettings
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_context.graph_context_request import GraphContextRequest
from app.domain.dtos.graph.graph_context.graph_context_response import (
    GraphContextFact,
    GraphContextResponse,
)
from app.domain.dtos.graph.graph_entity.graph_entity_response import GraphEntityResponse
from app.domain.dtos.graph.graph_entity.graph_relation_response import GraphRelationResponse
from app.infrastructure.http.authentication_provider.request_token import get_request_token
from app.infrastructure.http.document_collection_catalog.interfaces.document_collection_catalog_client_interface import (
    DocumentCollectionCatalogClientInterface,
)
from app.infrastructure.persistence.graph.repositories.interfaces.graph_entity_repository_interface import (
    GraphEntityRepositoryInterface,
)
from app.infrastructure.persistence.graph.repositories.interfaces.graph_relation_repository_interface import (
    GraphRelationRepositoryInterface,
)

logger = logging.getLogger(__name__)

_PREFIX_MATCHES_PER_TERM = 3
_MAX_PROVENANCE_DOCS_SHOWN = 5


class GraphContextService(GraphContextServiceInterface):
    def __init__(
            self,
            *,
            entity_repository: GraphEntityRepositoryInterface,
            relation_repository: GraphRelationRepositoryInterface,
            document_collection_catalog_client: DocumentCollectionCatalogClientInterface,
            knowledge_graph_settings: Optional[KnowledgeGraphSettings] = None,
    ) -> None:
        self._entity_repository = entity_repository
        self._relation_repository = relation_repository
        self._document_collection_catalog_client = document_collection_catalog_client
        self._settings = knowledge_graph_settings or KnowledgeGraphSettings()

    async def get_context(
            self,
            *,
            request: GraphContextRequest,
            authenticated_user: AuthenticatedUser,
            database_session: AsyncSession,
            authorization_header: str | None = None,
    ) -> GraphContextResponse:
        accessible_ids = await self._resolve_accessible_ids(
            user_id=int(authenticated_user.id),
            authorization_header=authorization_header,
        )
        if not accessible_ids:
            return GraphContextResponse()

        max_entities = min(request.max_entities, self._settings.context_max_entities)
        max_relations = min(request.max_relations, self._settings.context_max_relations)

        entities, matched_terms = await self._match_entities(
            terms=request.terms,
            question=request.question,
            accessible_ids=accessible_ids,
            max_entities=max_entities,
        )
        if not entities:
            return GraphContextResponse(matched_terms=matched_terms)

        relations = await self._collect_relations(
            entities=entities,
            accessible_ids=accessible_ids,
            max_relations=max_relations,
        )

        facts = self._build_facts(entities, relations)
        context_text = self._render_context_text(facts)

        logger.info(
            "Graph context built for RAG.",
            extra={
                "user_id": authenticated_user.id,
                "matched_terms": len(matched_terms),
                "entities": len(entities),
                "relations": len(relations),
                "context_chars": len(context_text),
            },
        )
        return GraphContextResponse(
            entities=entities,
            relations=relations,
            facts=facts,
            context_text=context_text,
            matched_terms=matched_terms,
        )

    async def _match_entities(
            self,
            *,
            terms: list[str],
            question: Optional[str],
            accessible_ids: list[int],
            max_entities: int,
    ) -> tuple[list[GraphEntityResponse], list[str]]:
        seen: dict[tuple[str, str], GraphEntityResponse] = {}
        matched_terms: list[str] = []

        for term in terms:
            canonical_term = self._canonicalize(term)
            if not canonical_term:
                continue
            try:
                matches = await self._entity_repository.search_by_name_prefix(
                    canonical_prefix=canonical_term,
                    entity_type=None,
                    accessible_document_ids=accessible_ids,
                    limit=_PREFIX_MATCHES_PER_TERM,
                )
            except Exception:
                logger.warning(
                    "Prefix entity match failed while building graph context (non-fatal).",
                    exc_info=True,
                )
                matches = []
            if matches:
                matched_terms.append(term)
            for entity in matches:
                seen.setdefault((entity.canonical_name, entity.type.value), entity)
            if len(seen) >= max_entities:
                break

        if len(seen) < max_entities:
            fulltext_input = question or " ".join(terms)
            if fulltext_input.strip():
                fulltext_matches = await self._entity_repository.fulltext_search(
                    query_string=fulltext_input,
                    entity_type=None,
                    accessible_document_ids=accessible_ids,
                    limit=max_entities,
                )
                for entity in fulltext_matches:
                    seen.setdefault((entity.canonical_name, entity.type.value), entity)
                    if len(seen) >= max_entities:
                        break

        return list(seen.values())[:max_entities], matched_terms

    async def _collect_relations(
            self,
            *,
            entities: list[GraphEntityResponse],
            accessible_ids: list[int],
            max_relations: int,
    ) -> list[GraphRelationResponse]:
        per_entity_limit = max(1, max_relations // max(1, len(entities)))

        async def fetch(entity: GraphEntityResponse) -> list[GraphRelationResponse]:
            try:
                return await self._relation_repository.list_neighbors_of(
                    canonical_name=entity.canonical_name,
                    entity_type=entity.type,
                    depth=self._settings.context_neighbor_depth,
                    relation_types=None,
                    accessible_document_ids=accessible_ids,
                    limit=per_entity_limit,
                )
            except Exception:
                logger.warning(
                    "Neighbor expansion failed while building graph context (non-fatal).",
                    extra={"canonical_name": entity.canonical_name},
                    exc_info=True,
                )
                return []

        results = await asyncio.gather(*(fetch(entity) for entity in entities))

        deduped: dict[tuple[str, str, str, str, str], GraphRelationResponse] = {}
        for relations in results:
            for relation in relations:
                key = (
                    relation.source.canonical_name,
                    relation.source.type.value,
                    relation.target.canonical_name,
                    relation.target.type.value,
                    relation.type,
                )
                existing = deduped.get(key)
                if existing is None or relation.confidence > existing.confidence:
                    deduped[key] = relation

        ordered = sorted(deduped.values(), key=lambda r: r.confidence, reverse=True)
        return ordered[:max_relations]

    @staticmethod
    def _build_facts(
            entities: list[GraphEntityResponse],
            relations: list[GraphRelationResponse],
    ) -> list[GraphContextFact]:
        facts: list[GraphContextFact] = []

        for entity in entities:
            if not entity.description:
                continue
            facts.append(
                GraphContextFact(
                    text=(
                        f"{entity.display_name} ({entity.type.value}): "
                        f"{entity.description}"
                    ),
                    source_document_ids=entity.source_document_ids[:_MAX_PROVENANCE_DOCS_SHOWN],
                )
            )

        for relation in relations:
            relation_label = relation.type.replace("_", " ")
            facts.append(
                GraphContextFact(
                    text=(
                        f"{relation.source.display_name} —[{relation_label}]→ "
                        f"{relation.target.display_name}"
                    ),
                    source_document_ids=relation.source_document_ids[:_MAX_PROVENANCE_DOCS_SHOWN],
                )
            )

        return facts

    def _render_context_text(self, facts: list[GraphContextFact]) -> str:
        if not facts:
            return ""
        lines: list[str] = []
        total = 0
        budget = self._settings.context_max_chars
        for fact in facts:
            docs_suffix = (
                f" [docs: {', '.join(str(d) for d in fact.source_document_ids)}]"
                if fact.source_document_ids
                else ""
            )
            line = f"- {fact.text}{docs_suffix}"
            if total + len(line) + 1 > budget:
                break
            lines.append(line)
            total += len(line) + 1
        return "\n".join(lines)

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

    @staticmethod
    def _canonicalize(name: str) -> str:
        if not name:
            return ""
        return " ".join(name.strip().lower().split())

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.graph.graph_extraction_service.exceptions.graph_extraction_service_exception import (
    GraphExtractionAlreadyRunningException,
    GraphExtractionDocumentNotFoundException,
)
from app.application.services.graph.graph_extraction_service.interfaces.graph_extraction_service_interface import (
    GraphExtractionServiceInterface,
)
from app.application.services.graph.knowledge_graph_settings import KnowledgeGraphSettings
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.processing_status import ProcessingStatus
from app.domain.constants.graph.relation_type import normalize_relation_type
from app.domain.dtos.graph.graph_field_limits import MAX_KG_ERROR_MESSAGE_CHARS
from app.domain.dtos.graph.graph_extraction.extracted_entity import ExtractedEntity
from app.domain.dtos.graph.graph_extraction.extracted_relation import ExtractedRelation
from app.domain.dtos.graph.graph_extraction.graph_extraction_progress import (
    GraphExtractionError,
    GraphExtractionProgressResponse,
)
from app.domain.dtos.graph.graph_extraction.graph_upsert_items import (
    EntityUpsertItem,
    RelationUpsertItem,
)
from app.infrastructure.http.llm_provider.llm_provider_interface import LlmProviderInterface
from app.infrastructure.persistence.database.database_manager.database_manager_interface import (
    DatabaseManagerInterface,
)
from app.infrastructure.persistence.database.orm.fragment import Fragment
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository_interface import (
    FragmentRepositoryInterface,
)
from app.infrastructure.persistence.graph.repositories.graph_entity_repository.graph_entity_repository_interface import (
    GraphEntityRepositoryInterface,
)
from app.infrastructure.persistence.graph.repositories.graph_relation_repository.graph_relation_repository_interface import (
    GraphRelationRepositoryInterface,
)
from app.infrastructure.persistence.memory_database.graph_extraction_job_progress_store.graph_extraction_job_progress_store_interface import (
    GraphExtractionJobProgressStoreInterface,
)

logger = logging.getLogger(__name__)


class GraphExtractionService(GraphExtractionServiceInterface):
    def __init__(
            self,
            *,
            database_manager: DatabaseManagerInterface,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            llm_provider: LlmProviderInterface,
            entity_repository: GraphEntityRepositoryInterface,
            relation_repository: GraphRelationRepositoryInterface,
            job_progress_store: GraphExtractionJobProgressStoreInterface,
            knowledge_graph_settings: Optional[KnowledgeGraphSettings] = None,
    ) -> None:
        self._database_manager = database_manager
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._llm_provider = llm_provider
        self._entity_repository = entity_repository
        self._relation_repository = relation_repository
        self._job_progress_store = job_progress_store
        self._settings = knowledge_graph_settings or KnowledgeGraphSettings()

    async def extract_for_document(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
            force: bool = False,
            message_id: Optional[str] = None,
    ) -> None:
        job_id = uuid.uuid4().hex
        logger.info(
            "Knowledge graph extraction was initiated.",
            extra={
                "document_id": document_id,
                "user_id": user.id,
                "job_id": job_id,
                "force": force,
                "message_id": message_id,
            },
        )

        if force:
            await self._job_progress_store.release_extraction_lock(document_id=document_id)
            logger.info(
                "Force flag set; any existing extraction lock was released.",
                extra={"document_id": document_id, "user_id": user.id},
            )

        acquired = await self._job_progress_store.try_acquire_extraction_lock(
            document_id=document_id,
            job_id=job_id,
        )
        if not acquired:
            logger.info(
                "Skipping knowledge graph extraction; another job is in progress.",
                extra={"document_id": document_id, "user_id": user.id},
            )
            raise GraphExtractionAlreadyRunningException(
                "A graph extraction job is already running for this document."
            )

        try:
            await self._run_job(
                job_id=job_id,
                document_id=document_id,
                user=user,
            )
            await self._set_graph_status(document_id, ProcessingStatus.processed)
        except Exception:
            await self._set_graph_status(document_id, ProcessingStatus.failed)
            raise
        finally:
            await self._job_progress_store.complete_job(
                job_id=job_id,
                document_id=document_id,
            )
            await self._job_progress_store.release_extraction_lock(
                document_id=document_id,
                job_id=job_id,
            )

    async def _set_graph_status(
            self,
            document_id: int,
            status: ProcessingStatus,
    ) -> None:
        try:
            async def _operation(session: AsyncSession) -> None:
                document = await self._document_repository.get_document_by_id(
                    document_id=document_id,
                    database_session=session,
                )
                if document is None:
                    return
                document.graph_status = status
                await self._document_repository.update_document(
                    document=document,
                    database_session=session,
                )

            await self._database_manager.run_write_transaction_with_retry(
                _operation,
                operation_name="graph_extraction.set_graph_status",
            )
        except Exception:
            logger.warning(
                "Failed to update the document graph status.",
                extra={"document_id": document_id, "graph_status": status.value},
            )

    async def get_progress(
            self,
            *,
            document_id: int,
    ) -> GraphExtractionProgressResponse:
        snapshot = await self._job_progress_store.get_snapshot(document_id=document_id)
        if snapshot is None:
            return GraphExtractionProgressResponse(
                job_id=None,
                document_id=document_id,
                is_running=False,
                total_fragments=0,
                processed_fragments=0,
                failed_fragments=0,
                extracted_entities=0,
                extracted_relations=0,
                started_at=None,
                finished_at=None,
                errors=[],
            )

        errors_raw = snapshot.get("errors") or []
        errors = []
        for item in errors_raw:
            try:
                errors.append(GraphExtractionError.model_validate(item))
            except Exception:
                continue

        return GraphExtractionProgressResponse(
            job_id=snapshot.get("job_id"),
            document_id=document_id,
            is_running=bool(snapshot.get("is_running")),
            total_fragments=int(snapshot.get("total_fragments", 0)),
            processed_fragments=int(snapshot.get("processed_fragments", 0)),
            failed_fragments=int(snapshot.get("failed_fragments", 0)),
            extracted_entities=int(snapshot.get("extracted_entities", 0)),
            extracted_relations=int(snapshot.get("extracted_relations", 0)),
            started_at=self._parse_optional_datetime(snapshot.get("started_at")),
            finished_at=self._parse_optional_datetime(snapshot.get("finished_at")),
            errors=errors,
        )

    async def _run_job(
            self,
            *,
            job_id: str,
            document_id: int,
            user: AuthenticatedUser,
    ) -> None:
        fragments = await self._load_fragments(document_id)
        await self._job_progress_store.begin_job(
            job_id=job_id,
            document_id=document_id,
            total_fragments=len(fragments),
        )

        if not fragments:
            logger.info(
                "No fragments were found for the document; finishing the extraction job.",
                extra={"document_id": document_id, "job_id": job_id},
            )
            return

        max_fragments = self._settings.extraction_max_fragments_per_document
        if len(fragments) > max_fragments:
            logger.warning(
                "Document has more fragments than the configured limit; truncating.",
                extra={
                    "document_id": document_id,
                    "fragment_count": len(fragments),
                    "limit": max_fragments,
                },
            )
            fragments = fragments[:max_fragments]

        allowed_entity_types = self._settings.resolve_allowed_entity_types()
        allowed_relation_types = self._settings.resolve_allowed_relation_types() or None

        window_chars = self._settings.extraction_sliding_window_chars
        if window_chars > 0:
            fragments.sort(key=lambda f: (f.fragment_index, int(f.id)))
            prev_tail = ""
            for fragment in fragments:
                prev_tail = await self._process_single_fragment(
                    job_id=job_id,
                    document_id=document_id,
                    fragment=fragment,
                    user=user,
                    allowed_entity_types=allowed_entity_types,
                    allowed_relation_types=allowed_relation_types,
                    prev_context_tail=prev_tail,
                )
        else:
            semaphore = asyncio.Semaphore(self._settings.extraction_concurrency)

            async def _runner(fragment: Fragment) -> None:
                async with semaphore:
                    await self._process_single_fragment(
                        job_id=job_id,
                        document_id=document_id,
                        fragment=fragment,
                        user=user,
                        allowed_entity_types=allowed_entity_types,
                        allowed_relation_types=allowed_relation_types,
                    )

            results = await asyncio.gather(
                *(_runner(fragment) for fragment in fragments),
                return_exceptions=True,
            )
            for outcome in results:
                if isinstance(outcome, BaseException):
                    logger.exception(
                        "Unexpected unhandled exception in a concurrent fragment runner.",
                        extra={"document_id": document_id, "job_id": job_id},
                        exc_info=outcome,
                    )

        logger.info(
            "Knowledge graph extraction finished for the document.",
            extra={
                "document_id": document_id,
                "job_id": job_id,
                "fragment_count": len(fragments),
            },
        )

    async def _load_fragments(self, document_id: int) -> list[Fragment]:
        async with self._database_manager.session() as session:
            document = await self._document_repository.get_document_by_id(
                document_id=document_id,
                database_session=session,
            )
            if document is None:
                logger.warning(
                    "Document not found while extracting the knowledge graph.",
                    extra={"document_id": document_id},
                )
                raise GraphExtractionDocumentNotFoundException(
                    "The document was not found.",
                )
            return await self._fragment_repository.get_fragments_by_document_id(
                document_id=document_id,
                database_session=session,
            )

    async def _process_single_fragment(
            self,
            *,
            job_id: str,
            document_id: int,
            fragment: Fragment,
            user: AuthenticatedUser,
            allowed_entity_types: list[str],
            allowed_relation_types: Optional[list[str]],
            prev_context_tail: str = "",
    ) -> str:
        fragment_id = int(fragment.id)
        await self._job_progress_store.mark_progress(
            job_id=job_id,
            document_id=document_id,
            current_fragment_id=fragment_id,
        )

        content = self._build_fragment_content(fragment.content, prev_context_tail)

        try:
            response = await self._llm_provider.extract_entities_relations(
                content=content,
                document_id=document_id,
                fragment_id=fragment_id,
                allowed_entity_types=allowed_entity_types,
                allowed_relation_types=allowed_relation_types,
                authenticated_user=user,
            )
        except Exception as e:
            await self._record_fragment_error(
                job_id=job_id,
                document_id=document_id,
                fragment_id=fragment_id,
                error=e,
                stage="llm",
            )
            return self._content_tail(fragment.content)

        entity_items, relation_items = self._build_upsert_batches(
            entities=response.entities,
            relations=response.relations,
        )

        try:
            await self._entity_repository.upsert_entities(
                entities=entity_items,
                document_id=document_id,
                fragment_id=fragment_id,
            )
        except Exception as e:
            await self._record_fragment_error(
                job_id=job_id,
                document_id=document_id,
                fragment_id=fragment_id,
                error=e,
                stage="upsert_entity",
            )
            return self._content_tail(fragment.content)

        try:
            await self._relation_repository.upsert_relations(
                relations=relation_items,
                document_id=document_id,
                fragment_id=fragment_id,
            )
        except Exception as e:
            await self._record_fragment_error(
                job_id=job_id,
                document_id=document_id,
                fragment_id=fragment_id,
                error=e,
                stage="upsert_relation",
            )
            return self._content_tail(fragment.content)

        entities_count = len(entity_items)
        relations_count = len(relation_items)

        await self._job_progress_store.mark_progress(
            job_id=job_id,
            document_id=document_id,
            processed_increment=1,
            extracted_entities_increment=entities_count,
            extracted_relations_increment=relations_count,
        )
        logger.debug(
            "Fragment was extracted into the knowledge graph.",
            extra={
                "document_id": document_id,
                "fragment_id": fragment_id,
                "entities_count": entities_count,
                "relations_count": relations_count,
            },
        )
        return self._content_tail(fragment.content)

    def _build_fragment_content(self, content: str, prev_tail: str) -> str:
        if not prev_tail:
            return content
        return f"[CONTEXTO PREVIO]\n{prev_tail}\n[FIN CONTEXTO PREVIO]\n\n{content}"

    def _content_tail(self, content: str) -> str:
        window = self._settings.extraction_sliding_window_chars
        if window <= 0:
            return ""
        return content[-window:] if len(content) > window else content

    def _build_upsert_batches(
            self,
            *,
            entities: list[ExtractedEntity],
            relations: list[ExtractedRelation],
    ) -> tuple[list[EntityUpsertItem], list[RelationUpsertItem]]:
        """Deduplicate the LLM output for a fragment into two write batches.

        Entities are keyed by ``(canonical_name, type)``; aliases are unioned
        and the first non-empty description wins. Relation endpoints are added
        to the entity batch so the relation MATCH always finds its nodes.
        Relations are keyed by the full quintuple keeping the highest
        confidence seen in the fragment.
        """
        entity_map: dict[tuple[str, str], EntityUpsertItem] = {}

        def add_entity(
                name: str,
                entity_type: Any,
                aliases: list[str],
                description: Optional[str],
        ) -> Optional[str]:
            canonical = self._canonicalize_name(name)
            if not canonical:
                return None
            key = (canonical, entity_type.value)
            existing = entity_map.get(key)
            if existing is None:
                entity_map[key] = EntityUpsertItem(
                    canonical_name=canonical,
                    display_name=name,
                    entity_type=entity_type,
                    aliases=tuple(dict.fromkeys(a for a in aliases if a and a.strip())),
                    description=description,
                )
            else:
                merged_aliases = tuple(
                    dict.fromkeys(
                        [*existing.aliases, *(a for a in aliases if a and a.strip())]
                    )
                )
                entity_map[key] = existing.model_copy(
                    update={
                        "aliases": merged_aliases,
                        "description": existing.description or description,
                    }
                )
            return canonical

        for entity in entities:
            add_entity(entity.name, entity.type, list(entity.aliases), entity.description)

        relation_map: dict[tuple[str, str, str, str, str], RelationUpsertItem] = {}
        for relation in relations:
            source_canonical = self._canonicalize_name(relation.source.name)
            target_canonical = self._canonicalize_name(relation.target.name)
            if not source_canonical or not target_canonical:
                continue
            if (
                    source_canonical == target_canonical
                    and relation.source.type == relation.target.type
            ):
                continue
            add_entity(relation.source.name, relation.source.type, [], None)
            add_entity(relation.target.name, relation.target.type, [], None)
            relation_type = normalize_relation_type(relation.type)
            confidence = float(max(0.0, min(1.0, relation.confidence)))
            key = (
                source_canonical,
                relation.source.type.value,
                target_canonical,
                relation.target.type.value,
                relation_type,
            )
            existing_relation = relation_map.get(key)
            if existing_relation is None or confidence > existing_relation.confidence:
                relation_map[key] = RelationUpsertItem(
                    source_canonical_name=source_canonical,
                    source_type=relation.source.type,
                    target_canonical_name=target_canonical,
                    target_type=relation.target.type,
                    relation_type=relation_type,
                    confidence=confidence,
                )

        return list(entity_map.values()), list(relation_map.values())

    async def _record_fragment_error(
            self,
            *,
            job_id: str,
            document_id: int,
            fragment_id: int,
            error: BaseException,
            stage: str,
    ) -> None:
        message = f"[{stage}] {type(error).__name__}: {str(error) or type(error).__name__}"[
            :MAX_KG_ERROR_MESSAGE_CHARS
        ]
        await self._job_progress_store.append_error(
            job_id=job_id,
            document_id=document_id,
            error=GraphExtractionError(
                fragment_id=fragment_id, error=message
            ).model_dump(mode="json"),
        )
        await self._job_progress_store.mark_progress(
            job_id=job_id,
            document_id=document_id,
            failed_increment=1,
        )
        logger.exception(
            "A fragment failed during knowledge graph extraction.",
            extra={
                "document_id": document_id,
                "fragment_id": fragment_id,
                "stage": stage,
            },
        )

    @staticmethod
    def _canonicalize_name(name: str) -> str:
        if not name:
            return ""
        return " ".join(name.strip().lower().split())

    @staticmethod
    def _parse_optional_datetime(value: object) -> Optional[datetime]:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

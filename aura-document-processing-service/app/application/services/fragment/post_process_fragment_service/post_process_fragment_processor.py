import asyncio
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.fragment.post_process_fragment_service.interfaces.post_process_fragment_processor_interface import (
    PostProcessFragmentProcessorInterface,
)
from app.application.services.fragment.post_process_fragment_service.post_process_fragment_service_settings import (
    PostProcessFragmentServiceSettings,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.processing_status import ProcessingStatus
from app.infrastructure.http.llm_provider.llm_provider_interface import LlmProviderInterface
from app.infrastructure.persistence.database.database_manager.database_manager_interface import (
    DatabaseManagerInterface,
)
from app.infrastructure.persistence.database.orm.fragment import Fragment
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository_interface import (
    FragmentRepositoryInterface,
)

logger = logging.getLogger(__name__)


class PostProcessFragmentProcessor(PostProcessFragmentProcessorInterface):
    def __init__(
            self,
            database_manager: DatabaseManagerInterface,
            fragment_repository: FragmentRepositoryInterface,
            llm_provider: LlmProviderInterface,
            post_process_fragment_service_settings: Optional[PostProcessFragmentServiceSettings] = None,
    ) -> None:
        self._database_manager = database_manager
        self._fragment_repository = fragment_repository
        self._llm_provider = llm_provider
        self._settings = post_process_fragment_service_settings or PostProcessFragmentServiceSettings()

    async def process_document_fragments(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
    ) -> None:
        fragments = await self._load_fragments(document_id)
        if not fragments:
            logger.info(
                "No fragments were found for the document; nothing to enrich.",
                extra={"document_id": document_id},
            )
            return

        semaphore = asyncio.Semaphore(self._settings.concurrency)

        async def _runner(fragment: Fragment) -> None:
            async with semaphore:
                await self._process_single_fragment(
                    document_id=document_id,
                    fragment=fragment,
                    user=user,
                )

        results = await asyncio.gather(
            *(_runner(fragment) for fragment in fragments),
            return_exceptions=True,
        )
        for outcome in results:
            if isinstance(outcome, BaseException):
                logger.exception(
                    "A fragment failed during post-processing; continuing with the rest.",
                    extra={"document_id": document_id},
                    exc_info=outcome,
                )

    async def _load_fragments(self, document_id: int) -> list[Fragment]:
        async with self._database_manager.session() as session:
            return await self._fragment_repository.get_fragments_by_document_id(
                document_id=document_id,
                database_session=session,
            )

    async def _process_single_fragment(
            self,
            *,
            document_id: int,
            fragment: Fragment,
            user: AuthenticatedUser,
    ) -> None:
        fragment_id = int(fragment.id)

        try:
            enriched = await self._llm_provider.enrich_fragment(
                content=fragment.content,
                authenticated_user=user,
            )

            async def _operation(session: AsyncSession) -> None:
                db_fragment = await self._fragment_repository.get_fragment_by_id(
                    fragment_id=fragment_id,
                    database_session=session,
                )
                if db_fragment is None:
                    raise ValueError(f"Fragment {fragment_id} was not found.")

                db_fragment.summary = enriched.summary
                db_fragment.entities = enriched.entities
                db_fragment.topics = enriched.topics
                db_fragment.enrichment_status = ProcessingStatus.processed

                await self._fragment_repository.update_fragment(
                    fragment=db_fragment,
                    database_session=session,
                )

            await self._database_manager.run_write_transaction_with_retry(
                _operation,
                operation_name="post_process_fragment.update_fragment_metadata",
            )
        except Exception:
            await self._mark_fragment_failed(fragment_id)
            raise

        logger.debug(
            "Fragment metadata was updated after enrichment.",
            extra={"document_id": document_id, "fragment_id": fragment_id},
        )

    async def _mark_fragment_failed(self, fragment_id: int) -> None:
        try:
            async def _operation(session: AsyncSession) -> None:
                db_fragment = await self._fragment_repository.get_fragment_by_id(
                    fragment_id=fragment_id,
                    database_session=session,
                )
                if db_fragment is None:
                    return
                db_fragment.enrichment_status = ProcessingStatus.failed
                await self._fragment_repository.update_fragment(
                    fragment=db_fragment,
                    database_session=session,
                )

            await self._database_manager.run_write_transaction_with_retry(
                _operation,
                operation_name="post_process_fragment.mark_fragment_failed",
            )
        except Exception:
            logger.warning(
                "Failed to mark the fragment enrichment status as failed.",
                extra={"fragment_id": fragment_id},
            )

import asyncio
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.services.fragment.contextualize_fragment_service.contextualize_fragment_service_settings import (
    ContextualizeFragmentServiceSettings,
)
from app.application.services.fragment.contextualize_fragment_service.interfaces.contextualize_fragment_processor_interface import (
    ContextualizeFragmentProcessorInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.processing_status import ProcessingStatus
from app.infrastructure.http.llm_provider.interfaces.llm_provider_interface import LlmProviderInterface
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import (
    DatabaseManagerInterface,
)
from app.infrastructure.persistence.database.orm.fragment import Fragment
from app.infrastructure.persistence.database.repositories.interfaces.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface,
)

logger = logging.getLogger(__name__)


class ContextualizeFragmentProcessor(ContextualizeFragmentProcessorInterface):
    """Builds a second, document-aware representation of each fragment.

    For every fragment it asks the LLM service for a short situating context based
    on the document summary, prepends it to the raw content, embeds the result and
    stores it in the dedicated contextualized columns. The original
    ``content``/``vector`` are never modified.
    """

    def __init__(
            self,
            database_manager: DatabaseManagerInterface,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            llm_provider: LlmProviderInterface,
            embedder_factory: EmbedderFactory,
            contextualize_fragment_service_settings: Optional[ContextualizeFragmentServiceSettings] = None,
    ) -> None:
        self._database_manager = database_manager
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._llm_provider = llm_provider
        self._embedder_factory = embedder_factory
        self._settings = contextualize_fragment_service_settings or ContextualizeFragmentServiceSettings()

    async def contextualize_document_fragments(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
    ) -> None:
        document_summary = await self._load_document_summary(document_id)
        if not document_summary:
            logger.warning(
                "The document has no summary available; skipping fragment contextualization.",
                extra={"document_id": document_id},
            )
            await self._mark_all_not_required(document_id, user)
            return

        document_summary = document_summary[: self._settings.max_document_summary_chars]

        fragments = await self._load_fragments(document_id)
        if not fragments:
            logger.info(
                "No fragments were found for the document; nothing to contextualize.",
                extra={"document_id": document_id},
            )
            return

        active_identity = self._embedder_factory.get_active_embedding_identity()
        pending = [f for f in fragments if not self._is_already_contextualized(f, active_identity)]
        skipped = len(fragments) - len(pending)
        if not pending:
            logger.info(
                "All fragments already contextualized on the active identity; nothing to do.",
                extra={"document_id": document_id, "fragment_count": len(fragments)},
            )
            return

        semaphore = asyncio.Semaphore(self._settings.concurrency)

        async def _runner(fragment: Fragment) -> None:
            async with semaphore:
                await self._contextualize_single_fragment(
                    document_id=document_id,
                    document_summary=document_summary,
                    fragment=fragment,
                    user=user,
                )

        results = await asyncio.gather(
            *(_runner(fragment) for fragment in pending),
            return_exceptions=True,
        )
        logger.info(
            "Fragment contextualization pass finished.",
            extra={"document_id": document_id, "processed": len(pending), "skipped": skipped},
        )
        for outcome in results:
            if isinstance(outcome, BaseException):
                logger.exception(
                    "A fragment failed during contextualization; continuing with the rest.",
                    extra={"document_id": document_id},
                    exc_info=outcome,
                )

    @staticmethod
    def _is_already_contextualized(fragment: Fragment, active_identity: str) -> bool:
        return (
            fragment.contextualization_status == ProcessingStatus.processed.value
            and bool(fragment.contextualized_content)
            and fragment.contextualized_embedding_identity == active_identity
        )

    async def _load_document_summary(self, document_id: int) -> Optional[str]:
        async with self._database_manager.session() as session:
            document = await self._document_repository.get_document_by_id(
                document_id=document_id,
                database_session=session,
            )
            if document is None:
                raise ValueError(f"Document {document_id} was not found.")
            summary = (document.description or "").strip()
            if summary:
                return summary
            return (document.name or "").strip() or None

    async def _load_fragments(self, document_id: int) -> list[Fragment]:
        async with self._database_manager.session() as session:
            return await self._fragment_repository.get_fragments_by_document_id(
                document_id=document_id,
                database_session=session,
            )

    async def _contextualize_single_fragment(
            self,
            *,
            document_id: int,
            document_summary: str,
            fragment: Fragment,
            user: AuthenticatedUser,
    ) -> None:
        fragment_id = int(fragment.id)
        content = (fragment.content or "").strip()
        if not content:
            await self._mark_failed(fragment_id, user)
            return

        try:
            contextualized = await self._llm_provider.contextualize_fragment(
                document_summary=document_summary,
                content=content,
                authenticated_user=user,
            )
            context = (contextualized.context or "").strip()
            contextualized_content = f"{context}\n\n{content}" if context else content

            vector = await self._embed(contextualized_content)
            identity = self._embedder_factory.get_active_embedding_identity()

            async def _operation(session: AsyncSession) -> None:
                await self._fragment_repository.update_fragment_contextualization(
                    fragment_id=fragment_id,
                    contextualized_content=contextualized_content,
                    contextualized_vector=vector,
                    contextualized_embedding_identity=identity,
                    status=ProcessingStatus.processed.value,
                    user_id=int(user.id),
                    database_session=session,
                )

            await self._database_manager.run_write_transaction_with_retry(
                _operation,
                operation_name="contextualize_fragment.update_fragment_contextualization",
            )
        except Exception:
            await self._mark_failed(fragment_id, user)
            raise

        logger.debug(
            "Fragment contextualized successfully.",
            extra={"document_id": document_id, "fragment_id": fragment_id},
        )

    async def _embed(self, text: str) -> list[float]:
        embeddings = await self._embedder_factory.embedder.aembed_documents([text])
        if not embeddings or len(embeddings) != 1:
            raise ValueError("The embedder did not return a single contextualized vector.")
        return embeddings[0]

    async def _mark_failed(self, fragment_id: int, user: AuthenticatedUser) -> None:
        await self._set_status(fragment_id, ProcessingStatus.failed, user)

    async def _mark_all_not_required(self, document_id: int, user: AuthenticatedUser) -> None:
        fragments = await self._load_fragments(document_id)
        for fragment in fragments:
            await self._set_status(int(fragment.id), ProcessingStatus.not_required, user)

    async def _set_status(
            self,
            fragment_id: int,
            status: ProcessingStatus,
            user: AuthenticatedUser,
    ) -> None:
        try:
            async def _operation(session: AsyncSession) -> None:
                await self._fragment_repository.update_fragment_contextualization_status(
                    fragment_id=fragment_id,
                    status=status.value,
                    user_id=int(user.id),
                    database_session=session,
                )

            await self._database_manager.run_write_transaction_with_retry(
                _operation,
                operation_name="contextualize_fragment.update_contextualization_status",
            )
        except Exception:
            logger.warning(
                "Failed to update the fragment contextualization status.",
                extra={"fragment_id": fragment_id, "contextualization_status": status.value},
            )

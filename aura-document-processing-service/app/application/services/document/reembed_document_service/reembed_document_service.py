import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.services.document.reembed_document_service.exceptions.reembed_document_service_exception import (
    ReembedDocumentNotFoundException,
    ReembedDocumentServiceException,
)
from app.application.services.document.reembed_document_service.interfaces.reembed_document_service_interface import (
    ReembedDocumentServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import (
    DatabaseManagerInterface,
)
from app.infrastructure.persistence.database.orm.fragment import Fragment
from app.infrastructure.persistence.database.repositories.exceptions.database_exceptions import DatabaseException
from app.infrastructure.persistence.database.repositories.interfaces.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface,
)

logger = logging.getLogger(__name__)


class ReembedDocumentService(ReembedDocumentServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            embedder_factory: EmbedderFactory,
            database_manager: DatabaseManagerInterface,
    ) -> None:
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._embedder_factory = embedder_factory
        self._database_manager = database_manager

    async def reembed_document(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
    ) -> int:
        logger.info(
            "Document re-embedding was initiated.",
            extra={"document_id": document_id, "user_id": user.id},
        )

        try:
            target_model = self._embedder_factory.get_active_model_name()
            target_dim = self._embedder_factory.get_vector_dimension()
            target_identity = self._embedder_factory.get_active_embedding_identity()

            async with self._database_manager.session() as session:
                document = await self._document_repository.get_document_by_id(
                    document_id=document_id,
                    database_session=session,
                )
                if document is None:
                    raise ReembedDocumentNotFoundException(
                        f"Document {document_id} was not found."
                    )
                fragments = await self._fragment_repository.get_fragments_for_reembedding(
                    document_id=document_id,
                    database_session=session,
                )

            raw_stale = [
                fragment for fragment in fragments
                if fragment.embedding_identity != target_identity
            ]
            contextual_stale = [
                fragment for fragment in fragments
                if fragment.contextualized_content
                and fragment.contextualized_embedding_identity != target_identity
            ]
            if not raw_stale and not contextual_stale:
                logger.info(
                    "No fragments require re-embedding; document is already on the active embedding identity.",
                    extra={"document_id": document_id, "model": target_model, "fragment_count": len(fragments)},
                )
                return 0

            raw_embeddings = (
                await self._embed_contents([fragment.content for fragment in raw_stale])
                if raw_stale else []
            )
            contextual_embeddings = (
                await self._embed_contents([fragment.contextualized_content for fragment in contextual_stale])
                if contextual_stale else []
            )

            await self._persist_reembeddings(
                user_id=int(user.id),
                raw_fragments=raw_stale,
                raw_embeddings=raw_embeddings,
                contextual_fragments=contextual_stale,
                contextual_embeddings=contextual_embeddings,
                target_model=target_model,
                target_dim=target_dim,
                target_identity=target_identity,
            )

            reembedded = len(raw_stale) + len(contextual_stale)
            logger.info(
                "Document re-embedding completed.",
                extra={
                    "document_id": document_id,
                    "model": target_model,
                    "raw_reembedded_count": len(raw_stale),
                    "contextual_reembedded_count": len(contextual_stale),
                    "total_fragments": len(fragments),
                },
            )
            return reembedded

        except ReembedDocumentServiceException:
            raise
        except DatabaseException as e:
            raise ReembedDocumentServiceException("Failed to persist re-embedded fragments.") from e
        except Exception as e:
            logger.exception(
                "An unexpected error occurred during document re-embedding.",
                extra={"document_id": document_id},
            )
            raise ReembedDocumentServiceException("Document re-embedding failed.") from e

    async def _embed_contents(self, contents: list[str]) -> list[list[float]]:
        embedder = self._embedder_factory.embedder
        embeddings: list[list[float]] = await embedder.aembed_documents(contents)
        if len(embeddings) != len(contents):
            raise ReembedDocumentServiceException(
                "The number of embeddings does not match the number of fragments."
            )
        return embeddings

    async def _persist_reembeddings(
            self,
            *,
            user_id: int,
            raw_fragments: list[Fragment],
            raw_embeddings: list[list[float]],
            contextual_fragments: list[Fragment],
            contextual_embeddings: list[list[float]],
            target_model: str,
            target_dim: int,
            target_identity: str,
    ) -> None:
        raw_ids = [int(fragment.id) for fragment in raw_fragments]
        contextual_ids = [int(fragment.id) for fragment in contextual_fragments]

        async def _operation(session: AsyncSession) -> None:
            for fragment_id, embedding in zip(raw_ids, raw_embeddings, strict=True):
                await self._fragment_repository.update_fragment_embedding(
                    fragment_id=fragment_id,
                    vector=embedding,
                    embedding_model=target_model,
                    embedding_dim=target_dim,
                    embedding_identity=target_identity,
                    user_id=user_id,
                    database_session=session,
                )
            for fragment_id, embedding in zip(contextual_ids, contextual_embeddings, strict=True):
                await self._fragment_repository.update_fragment_contextualized_embedding(
                    fragment_id=fragment_id,
                    contextualized_vector=embedding,
                    contextualized_embedding_identity=target_identity,
                    user_id=user_id,
                    database_session=session,
                )

        await self._database_manager.run_write_transaction_with_retry(
            _operation,
            operation_name="reembed_document.update_fragment_embeddings",
        )

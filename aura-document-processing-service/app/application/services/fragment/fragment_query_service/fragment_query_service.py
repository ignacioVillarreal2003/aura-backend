import logging
from typing import Optional
from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.helpers.authentication_helper import has_any_role
from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.services.fragment.fragment_query_service.exceptions.fragment_query_service_exception import (
    FragmentQueryEmbeddingException,
    FragmentQueryInvalidRequestException,
    FragmentQueryNotFoundException,
    FragmentQueryRetrievalException,
    FragmentQueryServiceException,
    FragmentQueryUnauthorizedException,
)
from app.application.services.fragment.fragment_query_service.fragment_query_service_authorizer import (
    FragmentQueryServiceAuthorizer
)
from app.application.services.fragment.fragment_query_service.fragment_query_service_validator import (
    FragmentQueryServiceValidator
)
from app.application.services.fragment.fragment_query_service.fragment_query_service_settings import (
    FragmentQueryServiceSettings
)
from app.application.services.fragment.fragment_query_service.interfaces.fragment_query_service_interface import (
    FragmentQueryServiceInterface
)
from app.domain.authentication.user_roles import ADMIN_ROLES
from app.domain.dtos.fragment.fragment_query_controller.documents_context_fragments_request import (
    DocumentsContextFragmentsRequest
)
from app.domain.dtos.fragment.fragment_query_controller.fragment_list_response import FragmentListResponse
from app.domain.dtos.fragment.fragment_query_controller.question_context_fragments_request import (
    QuestionContextFragmentsRequest
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.models import Document
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.database.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface
)

logger = logging.getLogger(__name__)


class FragmentQueryService(FragmentQueryServiceInterface):
    _KNOWN_EXCEPTIONS = (
        FragmentQueryNotFoundException,
        FragmentQueryUnauthorizedException,
        FragmentQueryInvalidRequestException,
        FragmentQueryEmbeddingException,
        FragmentQueryRetrievalException,
    )

    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            embedder_factory: EmbedderFactory,
            fragment_query_service_settings: Optional[FragmentQueryServiceSettings] = None
    ) -> None:
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._embedder_factory = embedder_factory
        self._settings = fragment_query_service_settings or FragmentQueryServiceSettings()
        self._validator = FragmentQueryServiceValidator(fragment_query_service_settings=self._settings)
        self._authorizer = FragmentQueryServiceAuthorizer()

    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser
    ) -> FragmentListResponse:
        question = question_context_fragments_request.question
        max_fragments = question_context_fragments_request.max_context_fragments

        logger.info(
            "Retrieve context fragments by question initiated",
            extra={"question_length": len(question), "max_fragments": max_fragments, "user_id": authenticated_user.id}
        )

        try:
            self._authorizer.require_permissions(authenticated_user=authenticated_user)
            self._authorizer.require_roles(
                authenticated_user,
                context="retrieve_context_fragments_by_question"
            )

            self._validator.validate_question_context_fragments_request(question_context_fragments_request)

            query_vector = await self._get_query_embedding(question)
            fragments = await self._retrieve_similar_fragments(
                database_session=database_session,
                query_vector=query_vector,
                k=max_fragments
            )

            logger.info(
                "Retrieve context fragments by question completed",
                extra={"question_length": len(question), "fragment_count": len(fragments)},
            )
            return FragmentListResponse(fragments=fragments)

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during retrieve context fragments by question",
                extra={"question_length": len(question)}
            )
            raise FragmentQueryServiceException(
                "Unexpected error retrieving context fragments by question"
            ) from e

    async def retrieve_context_fragments_by_documents(
            self,
            documents_context_fragments_request: DocumentsContextFragmentsRequest,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser
    ) -> FragmentListResponse:
        document_ids = documents_context_fragments_request.document_ids

        logger.info(
            "Retrieve context fragments by documents initiated",
            extra={"document_ids_count": len(document_ids), "user_id": authenticated_user.id}
        )
        logger.debug(
            "Retrieve context fragments by documents IDs payload",
            extra={"document_ids": document_ids}
        )

        try:
            self._authorizer.require_permissions(authenticated_user=authenticated_user)
            self._authorizer.require_roles(
                authenticated_user,
                context="retrieve_context_fragments_by_documents"
            )

            self._validator.validate_documents_context_fragments_request(documents_context_fragments_request)

            if not has_any_role(authenticated_user, ADMIN_ROLES):
                documents = await self._get_documents_by_ids_or_raise(
                    document_ids=document_ids,
                    database_session=database_session
                )
                for document in documents:
                    self._authorizer.require_ownership(document, authenticated_user)

            all_fragments = await self._retrieve_documents_fragments(
                database_session=database_session,
                document_ids=document_ids
            )

            logger.info(
                "Retrieve context fragments by documents completed",
                extra={"document_ids_count": len(document_ids), "fragment_count": len(all_fragments)}
            )
            return FragmentListResponse(fragments=all_fragments)

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during retrieve context fragments by documents",
                extra={"document_ids_count": len(document_ids)}
            )
            raise FragmentQueryServiceException(
                "Unexpected error retrieving context fragments for documents"
            ) from e

    async def _get_documents_by_ids_or_raise(
            self,
            document_ids: list[int],
            database_session: AsyncSession
    ) -> list[Document]:
        documents = await self._document_repository.get_documents_by_ids(
            document_ids=document_ids,
            database_session=database_session
        )
        found_ids = {document.id for document in documents}
        requested_ids = set(document_ids)
        not_found = sorted(requested_ids - found_ids)
        if not_found:
            logger.warning("Some documents not found", extra={"not_found_document_ids": not_found})
            raise FragmentQueryNotFoundException(f"Documents not found: {not_found}")
        return documents

    async def _get_query_embedding(self, question: str) -> list[float]:
        try:
            embedder = self._embedder_factory.embedder
            vector: list[float] = await embedder.aembed_query(text=question)
            logger.debug("Query embedding generated", extra={"question_length": len(question)})
            return vector
        except Exception as e:
            raise FragmentQueryEmbeddingException(
                f"Failed to generate query embedding: {e}"
            ) from e

    async def _retrieve_similar_fragments(
            self,
            database_session: AsyncSession,
            query_vector: list[float],
            k: int
    ) -> list:
        try:
            fragments = await self._fragment_repository.get_most_similar_fragments(
                query_vector=query_vector,
                database_session=database_session,
                k=k
            )
            logger.debug("Similar fragments retrieved", extra={"fragment_count": len(fragments)})
            return fragments
        except Exception as e:
            raise FragmentQueryRetrievalException(
                f"Failed to retrieve similar fragments: {e}"
            ) from e

    async def _retrieve_documents_fragments(
            self,
            database_session: AsyncSession,
            document_ids: list[int]
    ) -> list:
        try:
            fragments = await self._fragment_repository.get_fragments_by_document_ids(
                document_ids=document_ids,
                database_session=database_session
            )
            logger.debug(
                "Documents fragments retrieved",
                extra={"document_ids_count": len(document_ids), "fragment_count": len(fragments)}
            )
            return fragments
        except Exception as e:
            raise FragmentQueryRetrievalException(
                f"Failed to retrieve fragments for documents: {e}"
            ) from e


async def get_fragment_query_service(request: Request) -> FragmentQueryServiceInterface:
    try:
        return request.app.state.fragment_query_service
    except AttributeError:
        logger.error("FragmentQueryService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FragmentQueryService is not available",
        )

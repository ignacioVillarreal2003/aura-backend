import logging
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.services.document_query_service.document_query_service_request_validator import (
    DocumentQueryServiceRequestValidator
)
from app.application.services.document_query_service.document_query_service_settings import (
    DocumentQueryServiceSettings
)
from app.application.services.fragment_query_service.exceptions.fragment_query_service_exception import (
    FragmentQueryEmbeddingException,
    FragmentQueryInvalidRequestException,
    FragmentQueryNotFoundException,
    FragmentQueryRetrievalException,
    FragmentQueryServiceException,
    FragmentQueryUnauthorizedException,
)
from app.application.services.fragment_query_service.interfaces.fragment_query_service_interface import (
    FragmentQueryServiceInterface
)
from app.domain.dtos.fragment.fragment_query_controller.fragment_response import ContextFragmentListResponse
from app.domain.dtos.fragment.fragment_query_controller.question_context_fragments_request import QuestionContextFragmentsRequest
from app.domain.dtos.fragment.fragment_query_controller import DocumentsContextFragmentsRequest
from app.domain.models.document import Document
from app.infrastructure.http.authentication_provider.dtos.authenticated_user_response import AuthenticationResponse
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.database.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface
)

logger = logging.getLogger(__name__)


class FragmentQueryService(FragmentQueryServiceInterface):
    _ROLE_USER = "user"
    _ROLE_ADMIN = "admin"
    _ROLE_SUPERADMIN = "superadmin"

    _ADMIN_ROLES = {_ROLE_ADMIN, _ROLE_SUPERADMIN}
    _ALL_ALLOWED_ROLES = {_ROLE_USER, _ROLE_ADMIN, _ROLE_SUPERADMIN}

    _PERMISSION_DOCUMENT_GET = "DOCUMENT_GET"
    _REQUIRED_PERMISSIONS = {_PERMISSION_DOCUMENT_GET}

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
            document_query_service_settings: Optional[DocumentQueryServiceSettings] = None
    ) -> None:
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._embedder_factory = embedder_factory
        self._settings = document_query_service_settings or DocumentQueryServiceSettings()

        self._validator = DocumentQueryServiceRequestValidator(
            document_query_service_settings=self._settings
        )

    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse
    ) -> ContextFragmentListResponse:
        question = question_context_fragments_request.question
        max_fragments = question_context_fragments_request.max_context_fragments

        logger.info(
            "Retrieve context fragments by question initiated",
            extra={"question_length": len(question), "max_fragments": max_fragments, "user_id": authenticated_user.id}
        )

        try:
            self._require_permissions(authenticated_user)
            self._require_roles(
                authenticated_user, self._ALL_ALLOWED_ROLES,
                context="retrieve_context_fragments_by_question"
            )

            self._validator.validate_question_context_fragments_request(
                question_context_fragments_request
            )

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
            return ContextFragmentListResponse(context_fragments=fragments)

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
            authenticated_user: AuthenticationResponse
    ) -> ContextFragmentListResponse:
        document_ids = documents_context_fragments_request.document_ids

        logger.info(
            "Retrieve context fragments by documents initiated",
            extra={"document_ids": document_ids, "user_id": authenticated_user.id}
        )

        try:
            self._require_permissions(authenticated_user)
            self._require_roles(
                authenticated_user, self._ALL_ALLOWED_ROLES,
                context=f"retrieve_context_fragments_by_documents({document_ids})"
            )

            self._validate_document_ids(document_ids)

            if not self._has_any_role(authenticated_user, self._ADMIN_ROLES):
                for document_id in document_ids:
                    document = await self._get_document_or_raise(document_id, database_session)
                    self._require_ownership(document, authenticated_user)

            all_fragments = []
            for document_id in document_ids:
                fragments = await self._retrieve_document_fragments(
                    database_session=database_session,
                    document_id=document_id
                )
                all_fragments.extend(fragments)

            logger.info(
                "Retrieve context fragments by documents completed",
                extra={"document_ids": document_ids, "fragment_count": len(all_fragments)}
            )
            return ContextFragmentListResponse(context_fragments=all_fragments)

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during retrieve context fragments by documents",
                extra={"document_ids": document_ids}
            )
            raise FragmentQueryServiceException(
                f"Unexpected error retrieving context fragments for documents {document_ids}"
            ) from e

    def _require_permissions(self, authenticated_user: AuthenticationResponse) -> None:
        user_permissions = set(authenticated_user.permissions)
        missing = self._REQUIRED_PERMISSIONS - user_permissions

        if missing:
            logger.warning(
                "Insufficient permissions for fragment query operation",
                extra={
                    "user_id": authenticated_user.id,
                    "missing_permissions": sorted(missing),
                    "user_permissions": sorted(user_permissions)
                }
            )
            raise FragmentQueryUnauthorizedException(
                f"User {authenticated_user.id} is missing required permissions: {sorted(missing)}"
            )

    @staticmethod
    def _require_roles(
            authenticated_user: AuthenticationResponse,
            allowed_roles: set[str],
            context: str
    ) -> None:
        if not FragmentQueryService._has_any_role(authenticated_user, allowed_roles):
            logger.warning(
                "Insufficient role for fragment query operation",
                extra={
                    "user_id": authenticated_user.id,
                    "user_roles": sorted(authenticated_user.roles),
                    "allowed_roles": sorted(allowed_roles),
                    "context": context
                }
            )
            raise FragmentQueryUnauthorizedException(
                f"User {authenticated_user.id} does not have the required role for {context}. "
                f"Allowed roles: {sorted(allowed_roles)}"
            )

    @staticmethod
    def _require_ownership(document: Document, authenticated_user: AuthenticationResponse) -> None:
        if document.created_by != authenticated_user.id:
            logger.warning(
                "Unauthorized document access attempt",
                extra={
                    "document_id": document.id,
                    "owner_id": document.created_by,
                    "user_id": authenticated_user.id
                }
            )
            raise FragmentQueryUnauthorizedException(
                f"User {authenticated_user.id} is not authorized to access document {document.id}"
            )

    @staticmethod
    def _has_any_role(authenticated_user: AuthenticationResponse, roles: set[str]) -> bool:
        return bool(set(authenticated_user.roles) & roles)

    def _validate_document_ids(self, document_ids: list[int]) -> None:
        for document_id in document_ids:
            if document_id is None or document_id <= 0:
                raise FragmentQueryInvalidRequestException(
                    f"document_id must be a positive integer, got: {document_id!r}"
                )

    async def _get_document_or_raise(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> Document:
        document = await self._document_repository.get_document_by_id(
            document_id=document_id,
            database_session=database_session
        )
        if document is None:
            logger.warning("Document not found", extra={"document_id": document_id})
            raise FragmentQueryNotFoundException(f"Document {document_id} not found")
        return document

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

    async def _retrieve_document_fragments(
            self,
            database_session: AsyncSession,
            document_id: int
    ) -> list:
        try:
            fragments = await self._fragment_repository.get_fragments_by_document_id(
                document_id=document_id,
                database_session=database_session
            )
            logger.debug(
                "Document fragments retrieved",
                extra={"document_id": document_id, "fragment_count": len(fragments)}
            )
            return fragments
        except Exception as e:
            raise FragmentQueryRetrievalException(
                f"Failed to retrieve fragments for document {document_id}: {e}"
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

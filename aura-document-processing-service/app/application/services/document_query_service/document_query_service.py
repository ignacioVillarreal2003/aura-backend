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
from app.application.services.document_query_service.exceptions.document_query_service_exception import (
    DocumentQueryEmbeddingException,
    DocumentQueryFragmentRetrievalException,
    DocumentQueryInvalidRequestException,
    DocumentQueryNotFoundException,
    DocumentQueryServiceException,
    DocumentQueryUnauthorizedException
)
from app.application.services.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface
)
from app.domain.dtos.document_query_controller.context_fragment_response import ContextFragmentListResponse
from app.domain.dtos.document_query_controller.document_context_fragments_request import DocumentContextFragmentsRequest
from app.domain.dtos.document_query_controller.document_response import DocumentListResponse, DocumentResponse
from app.domain.dtos.document_query_controller.question_context_fragments_request import QuestionContextFragmentsRequest
from app.domain.models.document import Document
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.database.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface
)

logger = logging.getLogger(__name__)


class DocumentQueryService(DocumentQueryServiceInterface):
    _ROLE_USER = "user"
    _ROLE_ADMIN = "admin"
    _ROLE_SUPERADMIN = "superadmin"

    _ADMIN_ROLES = {_ROLE_ADMIN, _ROLE_SUPERADMIN}
    _ALL_ALLOWED_ROLES = {_ROLE_USER, _ROLE_ADMIN, _ROLE_SUPERADMIN}

    _PERMISSION_DOCUMENT_GET = "DOCUMENT_GET"
    _REQUIRED_PERMISSIONS = {_PERMISSION_DOCUMENT_GET}

    _KNOWN_EXCEPTIONS = (
        DocumentQueryNotFoundException,
        DocumentQueryUnauthorizedException,
        DocumentQueryInvalidRequestException,
        DocumentQueryEmbeddingException,
        DocumentQueryFragmentRetrievalException,
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

    async def get_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> DocumentResponse:
        logger.info(
            "Get document initiated",
            extra={"document_id": document_id, "user_id": user.id}
        )

        try:
            self._require_permissions(user)
            self._require_roles(user, self._ALL_ALLOWED_ROLES, context=f"get_document({document_id})")

            document = await self._get_document_or_raise(document_id, database_session)

            if not self._has_any_role(user, self._ADMIN_ROLES):
                self._require_ownership(document, user)

            logger.info(
                "Get document completed",
                extra={"document_id": document_id, "user_id": user.id}
            )
            return DocumentResponse.model_validate(document)

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception("Unexpected error during get document", extra={"document_id": document_id})
            raise DocumentQueryServiceException(
                f"Unexpected error retrieving document {document_id}"
            ) from e

    async def get_documents(
            self,
            database_session: AsyncSession,
            user: AuthenticationResponse,
            page: Optional[int] = None,
            size: Optional[int] = None
    ) -> DocumentListResponse:
        logger.info(
            "Get documents initiated",
            extra={"page": page, "size": size, "user_id": user.id}
        )

        try:
            self._require_permissions(user)
            self._require_roles(user, self._ADMIN_ROLES, context="get_documents")
            self._validator.validate_pagination(page, size)

            documents: list[Document] = await self._document_repository.get_documents(
                page=page,
                size=size,
                database_session=database_session
            )

            logger.info(
                "Get documents completed",
                extra={"page": page, "size": size, "count": len(documents), "user_id": user.id}
            )

            return DocumentListResponse(
                documents=[DocumentResponse.model_validate(d) for d in documents]
            )

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception("Unexpected error during get documents", extra={"page": page, "size": size})
            raise DocumentQueryServiceException("Unexpected error retrieving documents") from e

    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> ContextFragmentListResponse:
        question = question_context_fragments_request.question
        max_fragments = question_context_fragments_request.max_context_fragments

        logger.info(
            "Retrieve context fragments by question initiated",
            extra={"question_length": len(question), "max_fragments": max_fragments, "user_id": user.id}
        )

        try:
            self._require_permissions(user)
            self._require_roles(
                user, self._ALL_ALLOWED_ROLES,
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
            raise DocumentQueryServiceException(
                "Unexpected error retrieving context fragments by question"
            ) from e

    async def retrieve_context_fragments_by_document(
            self,
            document_context_fragments_request: DocumentContextFragmentsRequest,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> ContextFragmentListResponse:
        document_id = document_context_fragments_request.document_id

        logger.info(
            "Retrieve context fragments by document initiated",
            extra={"document_id": document_id, "user_id": user.id}
        )

        try:
            self._require_permissions(user)
            self._require_roles(
                user, self._ALL_ALLOWED_ROLES,
                context=f"retrieve_context_fragments_by_document({document_id})"
            )

            self._validator.validate_document_context_fragments_request(
                document_context_fragments_request
            )

            if not self._has_any_role(user, self._ADMIN_ROLES):
                document = await self._get_document_or_raise(document_id, database_session)
                self._require_ownership(document, user)

            fragments = await self._retrieve_document_fragments(
                database_session=database_session,
                document_id=document_id
            )

            logger.info(
                "Retrieve context fragments by document completed",
                extra={"document_id": document_id, "fragment_count": len(fragments)}
            )
            return ContextFragmentListResponse(context_fragments=fragments)

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during retrieve context fragments by document",
                extra={"document_id": document_id}
            )
            raise DocumentQueryServiceException(
                f"Unexpected error retrieving context fragments for document {document_id}"
            ) from e

    def _require_permissions(self, user: AuthenticationResponse) -> None:
        user_permissions = set(user.permissions)
        missing = self._REQUIRED_PERMISSIONS - user_permissions

        if missing:
            logger.warning(
                "Insufficient permissions for query operation",
                extra={
                    "user_id": user.id,
                    "missing_permissions": sorted(missing),
                    "user_permissions": sorted(user_permissions)
                }
            )
            raise DocumentQueryUnauthorizedException(
                f"User {user.id} is missing required permissions: {sorted(missing)}"
            )

    @staticmethod
    def _require_roles(
            user: AuthenticationResponse,
            allowed_roles: set[str],
            context: str
    ) -> None:
        if not DocumentQueryService._has_any_role(user, allowed_roles):
            logger.warning(
                "Insufficient role for query operation",
                extra={
                    "user_id": user.id,
                    "user_roles": sorted(user.roles),
                    "allowed_roles": sorted(allowed_roles),
                    "context": context
                }
            )
            raise DocumentQueryUnauthorizedException(
                f"User {user.id} does not have the required role for {context}. "
                f"Allowed roles: {sorted(allowed_roles)}"
            )

    @staticmethod
    def _require_ownership(document: Document, user: AuthenticationResponse) -> None:
        if document.created_by != user.id:
            logger.warning(
                "Unauthorized document access attempt",
                extra={
                    "document_id": document.id,
                    "owner_id": document.created_by,
                    "user_id": user.id
                }
            )
            raise DocumentQueryUnauthorizedException(
                f"User {user.id} is not authorized to access document {document.id}"
            )

    @staticmethod
    def _has_any_role(user: AuthenticationResponse, roles: set[str]) -> bool:
        return bool(set(user.roles) & roles)

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
            raise DocumentQueryNotFoundException(f"Document {document_id} not found")
        return document

    async def _get_query_embedding(self, question: str) -> list[float]:
        try:
            embedder = self._embedder_factory.embedder
            vector: list[float] = await embedder.aembed_query(text=question)
            logger.debug("Query embedding generated", extra={"question_length": len(question)})
            return vector
        except Exception as e:
            raise DocumentQueryEmbeddingException(
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
            raise DocumentQueryFragmentRetrievalException(
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
            raise DocumentQueryFragmentRetrievalException(
                f"Failed to retrieve fragments for document {document_id}: {e}"
            ) from e


async def get_document_query_service(request: Request) -> DocumentQueryServiceInterface:
    try:
        return request.app.state.document_query_service
    except AttributeError:
        logger.error("DocumentQueryService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentQueryService is not available",
        )

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio.session import AsyncSession
import logging

from app.api.controllers.document_controllers.document_query_controller.interfaces.document_query_controller_interface import (
    DocumentQueryControllerInterface
)
from app.application.services.document.document_query_service.document_query_service import get_document_query_service
from app.application.services.document.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface
)
from app.domain.constants.document.document_type import DocumentType
from app.domain.dtos.document.document_query.document_list_response import DocumentListResponse
from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session

logger = logging.getLogger(__name__)


class DocumentQueryController(DocumentQueryControllerInterface):
    async def get_document(
            self,
            document_id: int,
            document_query_service: DocumentQueryServiceInterface = Depends(get_document_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> DocumentResponse:
        logger.info(
            "Handling get document request",
            extra={
                "user_id": authenticated_user.id
            }
        )

        document_response = await document_query_service.get_document(
            document_id=document_id,
            database_session=database_session,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Get document completed successfully",
            extra={
                "user_id": authenticated_user.id
            }
        )

        return document_response

    async def get_documents(
            self,
            page: Optional[int] = Query(None),
            size: Optional[int] = Query(None),
            name: Optional[str] = Query(None),
            description: Optional[str] = Query(None),
            category: Optional[str] = Query(None),
            type: Optional[DocumentType] = Query(None),
            created_from: Optional[datetime] = Query(None),
            created_to: Optional[datetime] = Query(None),
            document_query_service: DocumentQueryServiceInterface = Depends(get_document_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> DocumentListResponse:
        logger.info(
            "Handling list documents request",
            extra={
                "user_id": authenticated_user.id
            }
        )

        document_list_response = await document_query_service.get_documents(
            database_session=database_session,
            authenticated_user=authenticated_user,
            page=page,
            size=size,
            name=name,
            description=description,
            category=category,
            type=type,
            created_from=created_from,
            created_to=created_to
        )

        logger.info(
            "List documents completed successfully",
            extra={
                "user_id": authenticated_user.id
            }
        )

        return document_list_response


    async def get_documents_by_chat(
            self,
            chat_id: int,
            document_query_service: DocumentQueryServiceInterface = Depends(get_document_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> DocumentListResponse:
        logger.info(
            "Handling get documents by chat request",
            extra={
                "user_id": authenticated_user.id
            }
        )

        document_list_response = await document_query_service.get_documents_by_chat(
            chat_id=chat_id,
            database_session=database_session,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Get documents by chat completed successfully",
            extra={
                "user_id": authenticated_user.id
            }
        )

        return document_list_response


router = APIRouter()
document_query_controller = DocumentQueryController()

router.get(
    "/document/{document_id}",
    response_model=DocumentResponse
)(document_query_controller.get_document)

router.get(
    "/documents",
    response_model=DocumentListResponse
)(document_query_controller.get_documents)

router.get(
    "/documents/chat/{chat_id}",
    response_model=DocumentListResponse
)(document_query_controller.get_documents_by_chat)

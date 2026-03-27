from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio.session import AsyncSession
import logging

from app.api.controllers.document.document_query_controller.interfaces.document_query_controller_interface import (
    DocumentQueryControllerInterface
)
from app.application.services.document_query_service.document_query_service import get_document_query_service
from app.application.services.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface
)
from app.domain.constants.document_type import DocumentType
from app.domain.dtos.document_query_controller.document_response import (
    DocumentResponse,
    DocumentListResponse
)
from app.infrastructure.authentication_provider.authentication_provider import get_current_user
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session

logger = logging.getLogger(__name__)


class DocumentQueryController(DocumentQueryControllerInterface):
    async def get_document(
            self,
            document_id: int,
            document_query_service: DocumentQueryServiceInterface = Depends(get_document_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticationResponse = Depends(get_current_user)
    ) -> DocumentResponse:
        logger.info(
            "Get document request received",
            extra={
                "document_id": document_id,
                "user_id": authenticated_user.id
            }
        )

        document_response = await document_query_service.get_document(
            document_id=document_id,
            database_session=database_session,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Get document request completed",
            extra={
                "document_id": document_id,
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
            authenticated_user: AuthenticationResponse = Depends(get_current_user)
    ) -> DocumentListResponse:
        logger.info(
            "Get documents request received",
            extra={
                "page": page,
                "size": size,
                "name": name,
                "category": category,
                "type": type,
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
            created_to=created_to,
        )

        logger.info(
            "Get documents request completed",
            extra={
                "page": page,
                "size": size,
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

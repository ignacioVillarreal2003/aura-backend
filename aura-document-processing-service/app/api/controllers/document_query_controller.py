from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio.session import AsyncSession
import logging

from app.api.controllers.interfaces.document_query_controller_interface import DocumentQueryControllerInterface
from app.application.services.document_query_service.document_query_service_dependency import get_document_query_service
from app.application.services.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface
)
from app.domain.dtos.document_query.document_list_response import DocumentListResponse
from app.domain.dtos.document_query.document_response import DocumentResponse
from app.infrastructure.authentication_provider.authentication_provider_dependency import (
    get_current_user
)
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.persistence.database.database_manager.database_manager_dependency import get_database_session

logger = logging.getLogger(__name__)


class DocumentQueryController(DocumentQueryControllerInterface):
    async def get_document_by_id(
            self,
            document_id: int,
            document_query_service: DocumentQueryServiceInterface = Depends(get_document_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            user: AuthenticationResponse = Depends(get_current_user)
    ) -> DocumentResponse:
        logger.info("Processing document deletion request")

        document_response = await document_query_service.get_document_by_id(
            document_id=document_id,
            database_session=database_session,
            user=user
        )

        logger.info("Document deletion request processed successfully")

        return document_response

    async def get_documents(
            self,
            page: Optional[int] = None,
            size: Optional[int] = None,
            document_query_service: DocumentQueryServiceInterface = Depends(get_document_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            user: AuthenticationResponse = Depends(get_current_user)
    ) -> DocumentListResponse:
        logger.info("Processing document deletion request")

        document_list_response = await document_query_service.get_documents(
            page=page,
            size=size,
            database_session=database_session,
            user=user
        )

        logger.info("Document deletion request processed successfully")

        return document_list_response


router = APIRouter()

document_query_controller = DocumentQueryController()

router.get(
    "/document/{document_id}",
    response_model=DocumentResponse
)(document_query_controller.get_document_by_id)

router.get(
    "/documents",
    response_model=DocumentListResponse
)(document_query_controller.get_documents)

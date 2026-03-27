from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio.session import AsyncSession
import logging

from app.api.controllers.document.delete_document_controller.interfaces.delete_document_controller_interface import (
    DeleteDocumentControllerInterface
)
from app.application.services.delete_document_service.delete_document_service import get_delete_document_service
from app.application.services.delete_document_service.interfaces.delete_document_service_interface import (
    DeleteDocumentServiceInterface
)
from app.infrastructure.authentication_provider.authentication_provider import get_current_user
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session

logger = logging.getLogger(__name__)


class DeleteDocumentController(DeleteDocumentControllerInterface):
    async def soft_delete_document(
            self,
            document_id: int,
            delete_document_service: DeleteDocumentServiceInterface = Depends(get_delete_document_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticationResponse = Depends(get_current_user)
    ) -> Response:
        logger.info(
            "Soft delete document request received",
            extra={
                "document_id": document_id,
                "user_id": authenticated_user.id
            }
        )

        await delete_document_service.soft_delete_document(
            document_id=document_id,
            database_session=database_session,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Soft delete document request completed",
            extra={
                "document_id": document_id,
                "user_id": authenticated_user.id
            }
        )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def soft_delete_documents_by_chat(
            self,
            chat_id: int,
            delete_document_service: DeleteDocumentServiceInterface = Depends(get_delete_document_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticationResponse = Depends(get_current_user)
    ) -> Response:
        logger.info(
            "Soft delete documents by chat request received",
            extra={
                "chat_id": chat_id,
                "user_id": authenticated_user.id
            }
        )

        await delete_document_service.soft_delete_documents_by_chat(
            chat_id=chat_id,
            database_session=database_session,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Soft delete documents by chat request completed",
            extra={
                "chat_id": chat_id,
                "user_id": authenticated_user.id
            }
        )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def hard_delete_document(
            self,
            document_id: int,
            delete_document_service: DeleteDocumentServiceInterface = Depends(get_delete_document_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticationResponse = Depends(get_current_user)
    ) -> Response:
        logger.info(
            "Hard delete document request received",
            extra={
                "document_id": document_id,
                "user_id": authenticated_user.id
            }
        )

        await delete_document_service.hard_delete_document(
            document_id=document_id,
            database_session=database_session,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Hard delete document request completed",
            extra={
                "document_id": document_id,
                "user_id": authenticated_user.id
            }
        )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def hard_delete_documents_by_chat(
            self,
            chat_id: int,
            delete_document_service: DeleteDocumentServiceInterface = Depends(get_delete_document_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticationResponse = Depends(get_current_user)
    ) -> Response:
        logger.info(
            "Hard delete documents by chat request received",
            extra={
                "chat_id": chat_id,
                "user_id": authenticated_user.id
            }
        )

        await delete_document_service.hard_delete_documents_by_chat(
            chat_id=chat_id,
            database_session=database_session,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Hard delete documents by chat request completed",
            extra={
                "chat_id": chat_id,
                "user_id": authenticated_user.id
            }
        )

        return Response(status_code=status.HTTP_204_NO_CONTENT)


router = APIRouter()

delete_document_controller = DeleteDocumentController()

router.delete(
    "/soft/document/{document_id}",
    response_model=None
)(delete_document_controller.soft_delete_document)

router.delete(
    "/soft/chat/{chat_id}",
    response_model=None
)(delete_document_controller.soft_delete_documents_by_chat)

router.delete(
    "/hard/document/{document_id}",
    response_model=None
)(delete_document_controller.hard_delete_document)

router.delete(
    "/hard/chat/{chat_id}",
    response_model=None
)(delete_document_controller.hard_delete_documents_by_chat)

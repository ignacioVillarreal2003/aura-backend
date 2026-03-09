from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio.session import AsyncSession
import logging

from app.api.controllers.document_query_controller.interfaces.document_query_controller_interface import (
    DocumentQueryControllerInterface
)
from app.application.services.document_query_service.document_query_service_dependency import get_document_query_service
from app.application.services.document_query_service.interfaces.document_query_service_interface import (

    DocumentQueryServiceInterface
)
from app.domain.dtos.document_query_controller.context_fragment_response import ContextFragmentListResponse
from app.domain.dtos.document_query_controller.document_response import (

    DocumentResponse,
    DocumentListResponse
)
from app.domain.dtos.document_query_controller.document_context_fragments_request import DocumentContextFragmentsRequest
from app.domain.dtos.document_query_controller.question_context_fragments_request import QuestionContextFragmentsRequest
from app.infrastructure.authentication_provider.authentication_provider_dependency import get_current_user
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.persistence.database.database_manager.database_manager_dependency import (
    get_database_session
)

logger = logging.getLogger(__name__)


class DocumentQueryController(DocumentQueryControllerInterface):
    async def get_document(
            self,
            document_id: int,
            document_query_service: DocumentQueryServiceInterface = Depends(get_document_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            user: AuthenticationResponse = Depends(get_current_user)
    ) -> DocumentResponse:
        logger.info(
            "Get document request received",
            extra={
                "document_id": document_id,
                "user_id": user.id
            }
        )

        document_response = await document_query_service.get_document(
            document_id=document_id,
            database_session=database_session,
            user=user
        )

        logger.info(
            "Get document request completed",
            extra={
                "document_id": document_id,
                "user_id": user.id
            }
        )

        return document_response

    async def get_documents(
            self,
            page: Optional[int] = None,
            size: Optional[int] = None,
            document_query_service: DocumentQueryServiceInterface = Depends(get_document_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            user: AuthenticationResponse = Depends(get_current_user)
    ) -> DocumentListResponse:
        logger.info(
            "Get documents request received",
            extra={
                "page": page,
                "size": size,
                "user_id": user.id
            }
        )

        document_list_response = await document_query_service.get_documents(
            database_session=database_session,
            user=user,
            page=page,
            size=size
        )

        logger.info(
            "Get documents request completed",
            extra={
                "page": page,
                "size": size,
                "user_id": user.id
            }
        )

        return document_list_response

    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            document_query_service: DocumentQueryServiceInterface = Depends(get_document_query_service),
            database_session: AsyncSession = Depends(get_database_session),
    ) -> ContextFragmentListResponse:
        logger.info(
            "Retrieve context fragments by question request received",
            extra={
                "question": question_context_fragments_request.question
            }
        )

        context_fragment_list_response = await document_query_service.retrieve_context_fragments_by_question(
            question_context_fragments_request=question_context_fragments_request,
            database_session=database_session
        )

        logger.info(
            "Retrieve context fragments by question request completed",
            extra={
                "question": question_context_fragments_request.question,
                "fragment_count": len(context_fragment_list_response.context_fragments)            }
        )

        return context_fragment_list_response

    async def retrieve_context_fragments_by_document(
            self,
            document_context_fragments_request: DocumentContextFragmentsRequest,
            document_query_service: DocumentQueryServiceInterface = Depends(get_document_query_service),
            database_session: AsyncSession = Depends(get_database_session),
    ) -> ContextFragmentListResponse:
        logger.info(
            "Retrieve context fragments by document request received",
            extra={
                "document_id": document_context_fragments_request.document_id
            }
        )

        context_fragment_list_response = await document_query_service.retrieve_context_fragments_by_document(
            document_context_fragments_request=document_context_fragments_request,
            database_session=database_session
        )

        logger.info(
            "Retrieve context fragments by document request completed",
            extra={
                "document_id": document_context_fragments_request.document_id,
                "fragment_count": len(context_fragment_list_response.context_fragments)            }
        )

        return context_fragment_list_response


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

router.post(
    "/retrieve-context-fragments-by-question",
    response_model=ContextFragmentListResponse
)(document_query_controller.retrieve_context_fragments_by_question)

router.post(
    "/retrieve-context-fragments-by-document",
    response_model=ContextFragmentListResponse
)(document_query_controller.retrieve_context_fragments_by_document)

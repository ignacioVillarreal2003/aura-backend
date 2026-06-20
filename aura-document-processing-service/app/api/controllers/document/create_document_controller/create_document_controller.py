from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.api.controllers.document.create_document_controller.interfaces.create_document_controller_interface import (
    CreateDocumentControllerInterface,
)
from app.api.dependencies.rate_limiter import strict_rate_limit
from app.api.openapi.common import default_error_responses
from app.api.schemas.document.create_document_form import parse_create_document_request
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.document.create_document_service.interfaces.create_document_service_interface import (
    CreateDocumentServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest
from app.domain.dtos.document.create_document.create_document_response import CreateDocumentResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session
from app.api.dependencies.services import get_create_document_service


class CreateDocumentController(CreateDocumentControllerInterface):
    async def create_document(
            self,
            create_document_request: CreateDocumentRequest = Depends(parse_create_document_request),
            file: UploadFile = File(...),
            create_document_service: CreateDocumentServiceInterface = Depends(get_create_document_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> CreateDocumentResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.DOCUMENT_CREATE}),
        )

        return await create_document_service.create_document(
            create_document_request=create_document_request,
            raw_document=file,
            database_session=database_session,
            authenticated_user=authenticated_user,
        )


router = APIRouter()
create_document_controller = CreateDocumentController()

_error = default_error_responses(
    include_400=True,
    include_404=False,
    include_413=True,
    include_415=True,
    include_502=True,
    include_503=True,
)
_response = {
    201: {
        "description": "Documento creado",
        "model": CreateDocumentResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    create_document_controller.create_document,
    methods=["POST"],
    response_model=CreateDocumentResponse,
    status_code=201,
    operation_id="createDocument",
    summary="Crear documento",
    description="Crea un documento a partir del archivo y los datos del formulario.",
    responses=_response,
)

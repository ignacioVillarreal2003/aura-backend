from fastapi import APIRouter, Depends, File, UploadFile

from app.api.controllers.document.bulk_create_document_controller.interfaces.bulk_create_document_controller_interface import (
    BulkCreateDocumentControllerInterface,
)
from app.api.dependencies.rate_limiter import strict_rate_limit
from app.api.dependencies.services import get_bulk_create_document_service
from app.api.openapi.common import default_error_responses
from app.api.schemas.document.bulk_create_document_form import parse_bulk_create_document_request
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.document.bulk_create_document_service.interfaces.bulk_create_document_service_interface import (
    BulkCreateDocumentServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest
from app.domain.dtos.document.bulk_create_document.bulk_create_document_response import (
    BulkCreateDocumentResponse,
)
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class BulkCreateDocumentController(BulkCreateDocumentControllerInterface):
    async def bulk_create_documents(
            self,
            create_document_request: CreateDocumentRequest = Depends(parse_bulk_create_document_request),
            files: list[UploadFile] = File(...),
            bulk_create_document_service: BulkCreateDocumentServiceInterface = Depends(
                get_bulk_create_document_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> BulkCreateDocumentResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.DOCUMENT_CREATE}),
        )

        return await bulk_create_document_service.bulk_create_documents(
            create_document_request=create_document_request,
            raw_documents=files,
            authenticated_user=authenticated_user,
        )


router = APIRouter()
bulk_create_document_controller = BulkCreateDocumentController()

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
        "description": "Lote de documentos procesado",
        "model": BulkCreateDocumentResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    bulk_create_document_controller.bulk_create_documents,
    methods=["POST"],
    response_model=BulkCreateDocumentResponse,
    status_code=201,
    operation_id="bulkCreateDocuments",
    summary="Crear documentos en lote",
    description=(
        "Crea varios documentos a partir de múltiples archivos en una sola "
        "solicitud. Cada archivo se procesa de forma independiente; la respuesta "
        "incluye el resultado por archivo (creado o fallido)."
    ),
    responses=_response,
)

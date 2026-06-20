import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.controllers.document.document_reembed_controller.interfaces.document_reembed_controller_interface import (
    DocumentReembedControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit, strict_rate_limit
from app.api.dependencies.services import get_bulk_dispatch_service
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.document.bulk_dispatch_service.exceptions.bulk_dispatch_service_exception import (
    BulkOperationConflictException,
    BulkOperationUnavailableException,
)
from app.application.services.document.bulk_dispatch_service.interfaces.bulk_dispatch_service_interface import (
    BulkDispatchServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document.bulk_operation import BulkOperation
from app.domain.dtos.document.bulk.bulk_responses import BulkJobStatusResponse, BulkStartResponse
from app.domain.dtos.document.reembed.reembed_request import ReembedRequest
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)

_OPERATION = BulkOperation.reembed
_REQUIRED = frozenset({Permissions.DOCUMENT_REEMBED_MANAGE})


class DocumentReembedController(DocumentReembedControllerInterface):
    async def reembed_manage(
            self,
            reembed_request: ReembedRequest,
            bulk_dispatch_service: BulkDispatchServiceInterface = Depends(get_bulk_dispatch_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> BulkStartResponse:
        Authorizer.require_permissions(authenticated_user=authenticated_user, required_permissions=_REQUIRED)
        try:
            return await bulk_dispatch_service.start(
                operation=_OPERATION,
                selector=reembed_request.selector,
                user=authenticated_user,
            )
        except BulkOperationConflictException as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
        except BulkOperationUnavailableException as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e

    async def status_manage(
            self,
            bulk_dispatch_service: BulkDispatchServiceInterface = Depends(get_bulk_dispatch_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> BulkJobStatusResponse:
        Authorizer.require_permissions(authenticated_user=authenticated_user, required_permissions=_REQUIRED)
        return await bulk_dispatch_service.status(operation=_OPERATION)

    async def stop_manage(
            self,
            bulk_dispatch_service: BulkDispatchServiceInterface = Depends(get_bulk_dispatch_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> BulkJobStatusResponse:
        Authorizer.require_permissions(authenticated_user=authenticated_user, required_permissions=_REQUIRED)
        return await bulk_dispatch_service.stop(operation=_OPERATION)


router = APIRouter()
document_reembed_controller = DocumentReembedController()

_error = default_error_responses(include_400=True, include_403=True, include_409=True, include_503=True)

router.add_api_route(
    "/manage",
    document_reembed_controller.reembed_manage,
    methods=["POST"],
    response_model=BulkStartResponse,
    status_code=202,
    operation_id="reembedDocumentsManage",
    summary="Re-embeber 1, varios o todos los documentos (manage)",
    description=(
        "Encola un re-embedding de los fragmentos existentes con el modelo activo para los "
        "documentos seleccionados (un id, varios ids, o todos via all_documents). Corre como "
        "un job en background; consultá el progreso en /status y detenelo en /stop."
    ),
    responses={202: {"description": "Job de re-embedding aceptado", "model": BulkStartResponse}, **_error},
)
router.add_api_route(
    "/manage/status",
    document_reembed_controller.status_manage,
    methods=["GET"],
    response_model=BulkJobStatusResponse,
    operation_id="getReembedJobStatusManage",
    summary="Estado del job de re-embedding (manage)",
    responses={200: {"description": "Estado del job", "model": BulkJobStatusResponse}, **_error},
)
router.add_api_route(
    "/manage/stop",
    document_reembed_controller.stop_manage,
    methods=["DELETE"],
    response_model=BulkJobStatusResponse,
    operation_id="stopReembedJobManage",
    summary="Detener el job de re-embedding en curso (manage)",
    responses={200: {"description": "Estado del job tras solicitar el stop", "model": BulkJobStatusResponse}, **_error},
)

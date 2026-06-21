import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.controllers.document.document_reprocess_controller.interfaces.document_reprocess_controller_interface import (
    DocumentReprocessControllerInterface,
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
from app.domain.dtos.document.reprocess.reprocess_request import ReprocessRequest
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)

_OPERATION = BulkOperation.reprocess
_REQUIRED = frozenset({Permissions.DOCUMENT_REPROCESS_MANAGE})


class DocumentReprocessController(DocumentReprocessControllerInterface):
    async def reprocess_manage(
            self,
            reprocess_request: ReprocessRequest,
            bulk_dispatch_service: BulkDispatchServiceInterface = Depends(get_bulk_dispatch_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> BulkStartResponse:
        Authorizer.require_permissions(authenticated_user=authenticated_user, required_permissions=_REQUIRED)
        try:
            return await bulk_dispatch_service.start(
                operation=_OPERATION,
                selector=reprocess_request.selector,
                user=authenticated_user,
                prefer_docling=reprocess_request.prefer_docling,
                enrich=reprocess_request.enrich,
                graph_extract=reprocess_request.graph_extract,
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
document_reprocess_controller = DocumentReprocessController()

_error = default_error_responses(include_400=True, include_403=True, include_409=True, include_503=True)

router.add_api_route(
    "/manage",
    document_reprocess_controller.reprocess_manage,
    methods=["POST"],
    response_model=BulkStartResponse,
    status_code=202,
    operation_id="reprocessDocumentsManage",
    summary="Reprocesar 1, varios o todos los documentos (manage)",
    description=(
        "Encola un reprocesamiento completo (re-download, re-chunk, re-embed) para los "
        "documentos seleccionados (un id, varios ids, o todos via all_documents): los "
        "fragmentos existentes se reemplazan. Corre como job en background; ver /status y /stop."
    ),
    responses={202: {"description": "Job de reprocesamiento aceptado", "model": BulkStartResponse}, **_error},
)
router.add_api_route(
    "/manage/status",
    document_reprocess_controller.status_manage,
    methods=["GET"],
    response_model=BulkJobStatusResponse,
    operation_id="getReprocessJobStatusManage",
    summary="Estado del job de reprocesamiento (manage)",
    responses={200: {"description": "Estado del job", "model": BulkJobStatusResponse}, **_error},
)
router.add_api_route(
    "/manage/stop",
    document_reprocess_controller.stop_manage,
    methods=["DELETE"],
    response_model=BulkJobStatusResponse,
    operation_id="stopReprocessJobManage",
    summary="Detener el job de reprocesamiento en curso (manage)",
    responses={200: {"description": "Estado del job tras solicitar el stop", "model": BulkJobStatusResponse}, **_error},
)

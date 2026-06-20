import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.controllers.document.document_enrich_controller.interfaces.document_enrich_controller_interface import (
    DocumentEnrichControllerInterface,
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
from app.domain.dtos.document.enrich.enrich_request import EnrichRequest
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)

_OPERATION = BulkOperation.enrich
_REQUIRED = frozenset({Permissions.DOCUMENT_ENRICH_MANAGE})


class DocumentEnrichController(DocumentEnrichControllerInterface):
    async def enrich_manage(
            self,
            enrich_request: EnrichRequest,
            bulk_dispatch_service: BulkDispatchServiceInterface = Depends(get_bulk_dispatch_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> BulkStartResponse:
        Authorizer.require_permissions(authenticated_user=authenticated_user, required_permissions=_REQUIRED)
        try:
            return await bulk_dispatch_service.start(
                operation=_OPERATION,
                selector=enrich_request.selector,
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
document_enrich_controller = DocumentEnrichController()

_error = default_error_responses(include_400=True, include_403=True, include_409=True, include_503=True)

router.add_api_route(
    "/manage",
    document_enrich_controller.enrich_manage,
    methods=["POST"],
    response_model=BulkStartResponse,
    status_code=202,
    operation_id="enrichDocumentsManage",
    summary="Enriquecer 1, varios o todos los documentos (manage)",
    description=(
        "Encola el enriquecimiento por LLM de los fragmentos existentes para los documentos "
        "seleccionados (un id, varios ids, o todos via all_documents). Es aditivo: actualiza "
        "los fragmentos en su lugar sin borrarlos ni re-chunkear. Corre como job en background; "
        "ver /status y /stop."
    ),
    responses={202: {"description": "Job de enriquecimiento aceptado", "model": BulkStartResponse}, **_error},
)
router.add_api_route(
    "/manage/status",
    document_enrich_controller.status_manage,
    methods=["GET"],
    response_model=BulkJobStatusResponse,
    operation_id="getEnrichJobStatusManage",
    summary="Estado del job de enriquecimiento (manage)",
    responses={200: {"description": "Estado del job", "model": BulkJobStatusResponse}, **_error},
)
router.add_api_route(
    "/manage/stop",
    document_enrich_controller.stop_manage,
    methods=["DELETE"],
    response_model=BulkJobStatusResponse,
    operation_id="stopEnrichJobManage",
    summary="Detener el job de enriquecimiento en curso (manage)",
    responses={200: {"description": "Estado del job tras solicitar el stop", "model": BulkJobStatusResponse}, **_error},
)

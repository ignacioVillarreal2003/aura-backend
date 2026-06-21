import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.controllers.graph.graph_extraction_controller.interfaces.graph_extraction_controller_interface import (
    GraphExtractionControllerInterface,
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
from app.domain.dtos.graph.graph_extraction.graph_reextract_request import GraphReextractRequest
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)

_OPERATION = BulkOperation.graph_extract
_REQUIRED = frozenset({Permissions.GRAPH_EXTRACT_MANAGE})


class GraphExtractionController(GraphExtractionControllerInterface):
    async def extract_manage(
            self,
            request: GraphReextractRequest,
            bulk_dispatch_service: BulkDispatchServiceInterface = Depends(get_bulk_dispatch_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> BulkStartResponse:
        Authorizer.require_permissions(authenticated_user=authenticated_user, required_permissions=_REQUIRED)
        try:
            return await bulk_dispatch_service.start(
                operation=_OPERATION,
                selector=request.selector,
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
graph_extraction_controller = GraphExtractionController()

_error = default_error_responses(include_400=True, include_403=True, include_409=True, include_503=True)

router.add_api_route(
    "/manage",
    graph_extraction_controller.extract_manage,
    methods=["POST"],
    response_model=BulkStartResponse,
    status_code=202,
    operation_id="extractGraphManage",
    summary="Extraer el grafo para 1, varios o todos los documentos (manage)",
    description=(
        "Encola la (re)extracción del grafo de conocimiento para los documentos seleccionados "
        "(un id, varios ids, o todos via all_documents). Es una reconstrucción idempotente: el "
        "footprint previo de cada documento se purga y se vuelve a extraer. Corre como job en "
        "background; ver /manage/status y /manage/stop."
    ),
    responses={202: {"description": "Job de extracción aceptado", "model": BulkStartResponse}, **_error},
)
router.add_api_route(
    "/manage/status",
    graph_extraction_controller.status_manage,
    methods=["GET"],
    response_model=BulkJobStatusResponse,
    operation_id="getGraphExtractionJobStatusManage",
    summary="Estado del job de extracción del grafo (manage)",
    responses={200: {"description": "Estado del job", "model": BulkJobStatusResponse}, **_error},
)
router.add_api_route(
    "/manage/stop",
    graph_extraction_controller.stop_manage,
    methods=["DELETE"],
    response_model=BulkJobStatusResponse,
    operation_id="stopGraphExtractionJobManage",
    summary="Detener el job de extracción del grafo en curso (manage)",
    responses={200: {"description": "Estado del job tras solicitar el stop", "model": BulkJobStatusResponse}, **_error},
)

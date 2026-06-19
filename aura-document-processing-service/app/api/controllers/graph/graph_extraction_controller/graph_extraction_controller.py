import logging
from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.controllers.graph.graph_extraction_controller.graph_extraction_controller_interface import (
    GraphExtractionControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit, strict_rate_limit
from app.api.dependencies.services import get_bulk_dispatch_service, get_graph_extraction_service
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
from app.application.services.graph.graph_extraction_service.interfaces.graph_extraction_service_interface import (
    GraphExtractionServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document.bulk_operation import BulkOperation
from app.domain.dtos.document.bulk.bulk_responses import BulkJobStatusResponse, BulkStartResponse
from app.domain.dtos.graph.graph_extraction.graph_extraction_progress import (
    GraphExtractionProgressResponse,
)
from app.domain.dtos.graph.graph_extraction.graph_reextract_request import GraphReextractRequest
from app.domain.field_limits import MAX_ID
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)

_OPERATION = BulkOperation.graph_extract
_REEXTRACT_REQUIRED = frozenset({Permissions.GRAPH_REEXTRACT})


class GraphExtractionController(GraphExtractionControllerInterface):
    async def get_extraction_progress(
            self,
            document_id: int = Path(..., ge=1, le=MAX_ID, description="ID del documento."),
            graph_extraction_service: GraphExtractionServiceInterface = Depends(
                get_graph_extraction_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> GraphExtractionProgressResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.GRAPH_EXTRACTION_PROGRESS}),
        )

        return await graph_extraction_service.get_progress(document_id=document_id)

    async def reextract(
            self,
            request: GraphReextractRequest,
            bulk_dispatch_service: BulkDispatchServiceInterface = Depends(get_bulk_dispatch_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> BulkStartResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=_REEXTRACT_REQUIRED,
        )
        try:
            return await bulk_dispatch_service.start(
                operation=_OPERATION,
                selector=request.selector,
                user=authenticated_user,
                force=request.force,
            )
        except BulkOperationConflictException as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
        except BulkOperationUnavailableException as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e

    async def batch_status(
            self,
            bulk_dispatch_service: BulkDispatchServiceInterface = Depends(get_bulk_dispatch_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> BulkJobStatusResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=_REEXTRACT_REQUIRED,
        )
        return await bulk_dispatch_service.status(operation=_OPERATION)

    async def stop(
            self,
            bulk_dispatch_service: BulkDispatchServiceInterface = Depends(get_bulk_dispatch_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> BulkJobStatusResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=_REEXTRACT_REQUIRED,
        )
        return await bulk_dispatch_service.stop(operation=_OPERATION)


router = APIRouter()
graph_extraction_controller = GraphExtractionController()

_error_progress = default_error_responses(include_400=False, include_403=True, include_503=True)

router.add_api_route(
    "/progress/{document_id}",
    graph_extraction_controller.get_extraction_progress,
    methods=["GET"],
    response_model=GraphExtractionProgressResponse,
    operation_id="getGraphExtractionProgress",
    summary="Consultar progreso de extracción del grafo (por documento)",
    description=(
        "Devuelve el estado actual del job de extracción del grafo de conocimiento "
        "para un documento dado. Si no hay job activo, devuelve is_running=False."
    ),
    responses=_error_progress,
)

_error_bulk = default_error_responses(include_400=True, include_403=True, include_409=True, include_503=True)

router.add_api_route(
    "/reextract",
    graph_extraction_controller.reextract,
    methods=["POST"],
    response_model=BulkStartResponse,
    status_code=202,
    operation_id="reextractKnowledgeGraph",
    summary="Re-extraer el grafo para 1, varios o todos los documentos",
    description=(
        "Encola la extracción del grafo de conocimiento para los documentos seleccionados "
        "(un id, varios ids, o todos via all_documents). Es aditivo: las entidades y "
        "relaciones se fusionan idempotentemente (MERGE). Corre como job en background; "
        "ver /batch-status y /stop."
    ),
    responses={202: {"description": "Job de extracción aceptado", "model": BulkStartResponse}, **_error_bulk},
)
router.add_api_route(
    "/batch-status",
    graph_extraction_controller.batch_status,
    methods=["GET"],
    response_model=BulkJobStatusResponse,
    operation_id="getGraphExtractionBatchStatus",
    summary="Estado del job masivo de extracción del grafo",
    responses={200: {"description": "Estado del job", "model": BulkJobStatusResponse}, **_error_bulk},
)
router.add_api_route(
    "/stop",
    graph_extraction_controller.stop,
    methods=["DELETE"],
    response_model=BulkJobStatusResponse,
    operation_id="stopGraphExtractionBatch",
    summary="Detener el job masivo de extracción del grafo",
    responses={200: {"description": "Estado del job tras solicitar el stop", "model": BulkJobStatusResponse}, **_error_bulk},
)

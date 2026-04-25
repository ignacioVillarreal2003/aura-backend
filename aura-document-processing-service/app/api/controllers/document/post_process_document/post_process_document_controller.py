from fastapi import APIRouter, Depends, Request, Response, status

from app.api.controllers.document.post_process_document.post_process_document_controller_interface import (
    PostProcessDocumentControllerInterface,
)
from app.api.dependencies.idempotency import optional_idempotency_key
from app.api.dependencies.rate_limiter import strict_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.services.document.post_process_document_service.interfaces.post_process_document_service_interface import (
    PostProcessDocumentServiceInterface,
)
from app.application.services.document.post_process_document_service.post_process_document_service import (
    get_post_process_document_service,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.post_process_document.post_process_documents_request import (
    PostProcessDocumentsRequest,
)
from app.domain.dtos.document.post_process_document.post_process_documents_start_response import (
    PostProcessDocumentsStartResponse,
)
from app.domain.dtos.document.post_process_document.post_process_documents_status_response import (
    PostProcessDocumentsStatusResponse,
)
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class PostProcessDocumentController(PostProcessDocumentControllerInterface):
    async def start_all(
            self,
            request: Request,
            post_process_document_service: PostProcessDocumentServiceInterface = Depends(
                get_post_process_document_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _idemp: None = Depends(optional_idempotency_key),
            _rl: None = Depends(strict_rate_limit),
    ) -> PostProcessDocumentsStartResponse:
        return await post_process_document_service.start_all(
            authenticated_user=authenticated_user,
        )

    async def start_for_documents(
            self,
            request: Request,
            post_process_documents_request: PostProcessDocumentsRequest,
            post_process_document_service: PostProcessDocumentServiceInterface = Depends(
                get_post_process_document_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _idemp: None = Depends(optional_idempotency_key),
            _rl: None = Depends(strict_rate_limit),
    ) -> PostProcessDocumentsStartResponse:
        return await post_process_document_service.start_for_documents(
            post_process_documents_request=post_process_documents_request,
            authenticated_user=authenticated_user,
        )

    async def get_status(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface = Depends(
                get_post_process_document_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
    ) -> PostProcessDocumentsStatusResponse:
        return await post_process_document_service.get_status(
            authenticated_user=authenticated_user,
        )

    async def stop(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface = Depends(
                get_post_process_document_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
    ) -> Response:
        await post_process_document_service.stop(authenticated_user=authenticated_user)
        return Response(status_code=status.HTTP_204_NO_CONTENT)


router = APIRouter()
post_process_document_controller = PostProcessDocumentController()

_error_start_all = default_error_responses(
    include_404=False,
    include_422=False,
    include_400=False,
    include_409=True,
    include_502=True,
    include_503=True,
)
_error_start_selected = default_error_responses(
    include_400=True,
    include_404=False,
    include_409=True,
    include_502=True,
    include_503=True,
)
_error_status = default_error_responses(
    include_404=False,
    include_422=False,
    include_429=False,
    include_503=True,
)
_error_stop = default_error_responses(
    include_400=True,
    include_404=False,
    include_422=False,
    include_429=False,
    include_503=True,
)
_response_start = {
    200: {
        "description": "Inicio aceptado",
        "model": PostProcessDocumentsStartResponse,
    },
    **_error_start_all,
}
_response_start_selected = {
    200: {
        "description": "Inicio aceptado",
        "model": PostProcessDocumentsStartResponse,
    },
    **_error_start_selected,
}
_response_status = {
    200: {
        "description": "Estado del post-proceso",
        "model": PostProcessDocumentsStatusResponse,
    },
    **_error_status,
}
_response_stop = {
    204: {
        "description": "Proceso detenido, sin cuerpo",
    },
    **_error_stop,
}

router.add_api_route(
    "/start",
    post_process_document_controller.start_all,
    methods=["POST"],
    response_model=PostProcessDocumentsStartResponse,
    operation_id="startPostProcessDocumentsAll",
    summary="Iniciar postproceso global",
    description="Inicia o reanuda el postproceso para todos los documentos.",
    responses=_response_start,
)
router.add_api_route(
    "/documents",
    post_process_document_controller.start_for_documents,
    methods=["POST"],
    response_model=PostProcessDocumentsStartResponse,
    operation_id="startPostProcessDocumentsSelected",
    summary="Iniciar postproceso por documentos",
    description="Inicia o reanuda el postproceso para los documentos enviados.",
    responses=_response_start_selected,
)
router.add_api_route(
    "/status",
    post_process_document_controller.get_status,
    methods=["GET"],
    response_model=PostProcessDocumentsStatusResponse,
    operation_id="getPostProcessDocumentsStatus",
    summary="Consultar estado del postproceso",
    description="Devuelve el estado actual del postproceso de documentos.",
    responses=_response_status,
)
router.add_api_route(
    "/stop",
    post_process_document_controller.stop,
    methods=["DELETE"],
    response_class=Response,
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="stopPostProcessDocuments",
    summary="Detener postproceso de documentos",
    description="Solicita detener el postproceso de documentos y responde 204.",
    responses=_response_stop,
)

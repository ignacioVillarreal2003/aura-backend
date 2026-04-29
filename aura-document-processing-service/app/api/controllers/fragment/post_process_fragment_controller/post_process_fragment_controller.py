from fastapi import APIRouter, Depends, Response, status

from app.api.controllers.fragment.post_process_fragment.post_process_fragment_controller_interface import (
    PostProcessFragmentControllerInterface,
)
from app.api.dependencies.idempotency import optional_idempotency_key
from app.api.dependencies.rate_limiter import default_rate_limit, strict_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.services.fragment.post_process_fragment_service.interfaces.post_process_fragment_service_interface import (
    PostProcessFragmentServiceInterface,
)
from app.application.services.fragment.post_process_fragment_service.post_process_fragment_service import (
    get_post_process_fragment_service,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.fragment.post_process_fragment.post_process_fragments_request import (
    PostProcessFragmentsRequest,
)
from app.domain.dtos.fragment.post_process_fragment.post_process_fragments_start_response import (
    PostProcessFragmentsStartResponse,
)
from app.domain.dtos.fragment.post_process_fragment.post_process_fragments_status_response import (
    PostProcessFragmentsStatusResponse,
)
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class PostProcessFragmentController(PostProcessFragmentControllerInterface):
    async def start_all(
            self,
            post_process_fragment_service: PostProcessFragmentServiceInterface = Depends(
                get_post_process_fragment_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _idemp: None = Depends(optional_idempotency_key),
            _rl: None = Depends(strict_rate_limit),
    ) -> PostProcessFragmentsStartResponse:
        return await post_process_fragment_service.start_all(
            authenticated_user=authenticated_user,
        )

    async def start_for_documents(
            self,
            post_process_fragments_request: PostProcessFragmentsRequest,
            post_process_fragment_service: PostProcessFragmentServiceInterface = Depends(
                get_post_process_fragment_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _idemp: None = Depends(optional_idempotency_key),
            _rl: None = Depends(strict_rate_limit),
    ) -> PostProcessFragmentsStartResponse:
        return await post_process_fragment_service.start_for_documents(
            post_process_fragments_request=post_process_fragments_request,
            authenticated_user=authenticated_user,
        )

    async def get_status(
            self,
            post_process_fragment_service: PostProcessFragmentServiceInterface = Depends(
                get_post_process_fragment_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> PostProcessFragmentsStatusResponse:
        return await post_process_fragment_service.get_status(
            authenticated_user=authenticated_user,
        )

    async def stop(
            self,
            post_process_fragment_service: PostProcessFragmentServiceInterface = Depends(
                get_post_process_fragment_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> Response:
        await post_process_fragment_service.stop(authenticated_user=authenticated_user)
        return Response(status_code=status.HTTP_204_NO_CONTENT)


router = APIRouter()
post_process_fragment_controller = PostProcessFragmentController()

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
    include_503=True,
)
_error_stop = default_error_responses(
    include_400=True,
    include_404=False,
    include_422=False,
    include_503=True,
)
_response_start = {
    202: {
        "description": "Inicio aceptado",
        "model": PostProcessFragmentsStartResponse,
    },
    **_error_start_all,
}
_response_start_selected = {
    202: {
        "description": "Inicio aceptado",
        "model": PostProcessFragmentsStartResponse,
    },
    **_error_start_selected,
}
_response_status = {
    200: {
        "description": "Estado del post-proceso de fragmentos",
        "model": PostProcessFragmentsStatusResponse,
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
    post_process_fragment_controller.start_all,
    methods=["POST"],
    response_model=PostProcessFragmentsStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="startPostProcessFragmentsAll",
    summary="Iniciar postproceso global",
    description="Inicia o reanuda el postproceso para todos los fragmentos.",
    responses=_response_start,
)
router.add_api_route(
    "/documents",
    post_process_fragment_controller.start_for_documents,
    methods=["POST"],
    response_model=PostProcessFragmentsStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="startPostProcessFragmentsSelected",
    summary="Iniciar postproceso por documentos",
    description="Inicia o reanuda el postproceso para fragmentos de los documentos enviados.",
    responses=_response_start_selected,
)
router.add_api_route(
    "/status",
    post_process_fragment_controller.get_status,
    methods=["GET"],
    response_model=PostProcessFragmentsStatusResponse,
    operation_id="getPostProcessFragmentsStatus",
    summary="Consultar estado del postproceso",
    description="Devuelve el estado actual del postproceso de fragmentos.",
    responses=_response_status,
)
router.add_api_route(
    "/stop",
    post_process_fragment_controller.stop,
    methods=["DELETE"],
    response_class=Response,
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="stopPostProcessFragments",
    summary="Detener postproceso de fragmentos",
    description="Solicita detener el postproceso de fragmentos y responde 204.",
    responses=_response_stop,
)

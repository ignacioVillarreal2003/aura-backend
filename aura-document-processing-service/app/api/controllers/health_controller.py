from fastapi import APIRouter
import logging

from app.api.controllers.interfaces.health_controller_interface import HealthControllerInterface
from app.configuration.environment_variables import environment_variables
from app.domain.dtos.health.health_response import HealthResponse

logger = logging.getLogger(__name__)


class HealthController(HealthControllerInterface):
    def get_status(
            self
    ) -> HealthResponse:
        return HealthResponse(
            status="healthy",
            app=environment_variables.app_name,
            version=environment_variables.app_version
        )


router = APIRouter()

health_controller = HealthController()

router.get(
    "",
    response_model=HealthResponse
)(health_controller.get_status)

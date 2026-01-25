import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.application.exceptions.app_exceptions import AppError
from app.application.services.agent_service.interfaces.agent_service_interface import AgentServiceInterface
from app.configuration.dependencies import get_agent_service
from app.domain.dtos.agent_request import AgentRequest
from app.domain.dtos.agent_response import AgentResponse

logger = logging.getLogger(__name__)


class AgentController:
    @staticmethod
    async def execute_agent(agent_request: AgentRequest,
                            agent_service: AgentServiceInterface = Depends(get_agent_service)) -> AgentResponse:
        logger.info("Processing agent_node request")

        try:
            agent_response: AgentResponse = await agent_service.execute_agent(agent_request)

            logger.info("Agent request processed successfully")

            return agent_response

        except AppError as e:
            logger.warning(
                "Application error in agent_node controller",
                extra={
                    "error_code": e.code,
                    "error_message": e.message,
                    "status_code": e.status_code
                }
            )
            raise HTTPException(
                status_code=e.status_code,
                detail={
                    "error": e.code,
                    "message": e.message
                }
            )

        except Exception as e:
            logger.exception(
                "Unexpected error in agent_node controller",
                extra={
                    "error_type": type(e).__name__
                }
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred while processing the agent_node request"
                }
            )


router = APIRouter()

agent_controller = AgentController()

router.post(
    "",
    response_model=AgentResponse
)(agent_controller.execute_agent)

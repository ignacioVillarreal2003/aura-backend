import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.application.exceptions.app_exceptions import AppError
from app.application.services.agent_service import AgentService
from app.configuration.dependencies import get_agent_service
from app.domain.dtos.agent_request import AgentRequest
from app.domain.dtos.agent_response import AgentResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Agent"],
    responses={
        400: {"description": "Bad Request"},
        500: {"description": "Internal Server Error"}
    }
)


class AgentController:
    async def execute_agent(self,
                            request_body: AgentRequest,
                            agent_service: AgentService = Depends(get_agent_service)) -> AgentResponse:
        logger.info(
            "Processing agent request",
            extra={
                "message": request_body.message
            }
        )

        try:
            response: AgentResponse = await agent_service.execute_agent(request_body)

            logger.info(
                "Agent request processed successfully",
                extra={
                    "answer": response.answer
                }
            )

            return response

        except AppError as e:
            logger.warning(
                "Application error in agent controller",
                extra={
                    "error_code": e.code,
                    "error_message": e.message,
                    "status_code": e.status_code,
                    "message": request_body.message
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
                "Unexpected error in agent controller",
                extra={
                    "error_type": type(e).__name__,
                    "message": request_body.message
                }
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred while processing the agent request"
                }
            )


agent_controller = AgentController()

router.post(
    "",
    response_model=AgentResponse,
    summary="Execute an agent request",
    description="Processes a user message through an agent that can automatically decide the workflow",
    response_description="Respond with an agent response",
    status_code=status.HTTP_200_OK
)(agent_controller.execute_agent)

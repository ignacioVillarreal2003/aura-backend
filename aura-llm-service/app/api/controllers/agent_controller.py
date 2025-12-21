import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.application.exceptions.app_exceptions import AppError
from app.application.services.agent_service import AgentService
from app.configuration.dependencies import get_agent_service
from app.domain.dtos.agent_request import AgentRequest
from app.domain.dtos.agent_response import AgentResponse

logger = logging.getLogger(__name__)

router = APIRouter()


class AgentController:
    async def execute_agent(self,
                            request_body: AgentRequest,
                            agent_service: AgentService = Depends(
                                get_agent_service)) -> AgentResponse:
        try:
            response = await agent_service.execute_agent(request_body)
            logger.info("Agent request processed successfully")
            return response
        except AppError as e:
            logger.warning(f"App error in controller: {e.message}")
            raise HTTPException(
                status_code=e.status_code,
                detail={
                    "error": e.code,
                    "message": e.message
                }
            )
        except Exception:
            logger.exception("Unexpected error")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred while generating the response",
                }
            )


controller = AgentController()
router.post("", response_model=AgentResponse)(controller.execute_agent)

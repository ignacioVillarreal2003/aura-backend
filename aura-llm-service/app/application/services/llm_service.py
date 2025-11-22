import logging
import httpx

from app.application.services.interfaces.llm_service_interface import LLMServiceInterface
from app.configuration.environment_variables import environment_variables
from app.application.exceptions.api_exceptions import LLMError

logger = logging.getLogger(__name__)


class LLMService(LLMServiceInterface):
    def __init__(self):
        self.ollama_url = environment_variables.ollama_url
        self.model_name = environment_variables.model_name

    async def call(self,
                   messages: list[dict]) -> dict:
        logger.info(f"Sending request to LLM model '{self.model_name}'", extra={
            "model": self.model_name,
            "message_count": len(messages)
        })

        try:
            payload = {
                "model": self.model_name,
                "messages": messages,
                "stream": False
            }

            async with httpx.AsyncClient(timeout=500) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json=payload
                )

                if response.status_code != 200:
                    logger.error(
                        f"Ollama returned a non-200 status code: {response.status_code}",
                        extra={
                            "status_code": response.status_code,
                            "response_text": response.text
                        }
                    )
                    raise LLMError(
                        f"La API de Ollama devolvió un error: {response.text}",
                        code="OLLAMA_API_ERROR"
                    )

                logger.info("Successfully received response from LLM.")
                return response.json()

        except httpx.TimeoutException:
            logger.error("Timeout while waiting for Ollama response.")
            raise LLMError(
                "El modelo tardó demasiado en responder.",
                code="OLLAMA_TIMEOUT"
            )

        except httpx.ConnectError:
            logger.error("Connection to Ollama failed", extra={"url": self.ollama_url})
            raise LLMError(
                f"No se pudo conectar a Ollama en: {self.ollama_url}",
                code="OLLAMA_CONNECTION_ERROR"
            )

        except httpx.HTTPError as e:
            logger.error(f"HTTP error communicating with Ollama: {str(e)}", extra={"error": str(e)})
            raise LLMError(
                f"Error de comunicación HTTP con Ollama: {str(e)}",
                code="OLLAMA_HTTP_ERROR"
            )

        except LLMError:
            raise

        except Exception as e:
            logger.exception(f"Unexpected error calling the LLM: {str(e)}", extra={"error": str(e)})
            raise LLMError(
                f"Error inesperado al comunicarse con el modelo: {str(e)}",
                code="OLLAMA_UNKNOWN_ERROR"
            )

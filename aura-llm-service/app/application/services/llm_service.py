import logging
import httpx

from app.configuration.environment_variables import environment_variables
from app.application.exceptions.api_exceptions import LLMError

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, model_name: str = "gemma3:1b"):
        self.ollama_url = environment_variables.ollama_url
        self.model_name = model_name

    async def call(self, messages: list[dict]) -> dict:
        try:
            payload = {
                "model": self.model_name,
                "messages": messages,
                "stream": False
            }

            logger.debug(f"Enviando request a Ollama (no stream): {self.ollama_url}/api/chat")

            async with httpx.AsyncClient(timeout=500.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json=payload
                )

                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Error de Ollama [{response.status_code}]: {error_detail}")
                    raise LLMError(
                        f"Error al comunicarse con Ollama: {error_detail}",
                        code="OLLAMA_API_ERROR"
                    )

                json_response = response.json()

                logger.debug(f"Respuesta del modelo: {json_response}")

                return json_response

        except httpx.TimeoutException as e:
            logger.error(f"Timeout al llamar a Ollama: {str(e)}")
            raise LLMError("El modelo tardó demasiado en responder.", code="OLLAMA_TIMEOUT")

        except httpx.ConnectError as e:
            logger.error(f"Error de conexión con Ollama: {str(e)}")
            raise LLMError(f"No se pudo conectar con Ollama en {self.ollama_url}.", code="OLLAMA_CONNECTION_ERROR")

        except httpx.HTTPError as e:
            logger.error(f"Error HTTP al llamar a Ollama: {str(e)}")
            raise LLMError(f"Error en la comunicación HTTP con Ollama: {str(e)}", code="OLLAMA_HTTP_ERROR")

        except LLMError:
            raise

        except Exception as e:
            logger.error(f"Error inesperado al llamar a Ollama: {str(e)}", exc_info=True)
            raise LLMError(f"Error inesperado al comunicarse con el modelo: {str(e)}", code="OLLAMA_UNKNOWN_ERROR")
# Aura LLM Service

## Variables de Entorno

### Entorno local

Crear un archivo `.env` en la raíz del proyecto con todas las variables:

```env
OLLAMA_URL=http://localhost:11434
MODEL_NAME=gemma3:1b
```

### Entorno Docker

Crear un archivo `.env.docker` con las variables adaptadas a los servicios de Docker:

```env
OLLAMA_URL=http://llm:11434
MODEL_NAME=gemma3:1b
```























from fastapi import HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage





@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:

        new_message = HumanMessage(content=request.message)

        # 3. Construir el estado INICIAL para esta ejecución
        # Nota: Pasamos 'history + [new_message]' para que el grafo tenga contexto
        initial_state = {
            "messages": history + [new_message],
            "sentiment": "neutral",  # Valor por defecto, el nodo lo actualizará
            "summary": ""
        }

        # 4. INVOCAR AL GRAFO
        # 'ainvoke' ejecuta todo el flujo (Sentimiento -> Agente -> Herramientas -> Agente)
        result = await app_agent.ainvoke(initial_state)

        # 5. Obtener la última respuesta generada por la IA
        # result["messages"] tendrá TODA la conversación acumulada en esta ejecución
        last_message = result["messages"][-1]

        # Validamos que sea una respuesta de IA y no una llamada a herramienta intermedia
        if not isinstance(last_message, AIMessage):
            # A veces el grafo puede devolver algo intermedio si no está bien cerrado,
            # pero con tu lógica debería ser siempre el último AIMessage.
            pass

        # 6. Guardar en Base de Datos (Persistencia)
        # Solo guardamos lo nuevo: lo que dijo el usuario y lo que respondió la IA final
        save_to_db(request.user_id, request.message, last_message.content)

        # 7. Responder al Frontend
        return {
            "response": last_message.content,
            "metadata": {
                "sentiment_detected": result.get("sentiment"),
                "tool_used": "Sí" if len(result["messages"]) > len(initial_state["messages"]) + 1 else "No"
            }
        }

    except Exception as e:
        # Manejo de errores
        raise HTTPException(status_code=500, detail=str(e))












from fastapi import APIRouter, Depends, HTTPException, status
import logging

from app.domain.dtos.agent_request import AgentRequest
from app.domain.dtos.agent_response import AgentResponse
from app.domain.dtos.document_summary_response import DocumentSummaryResponse
from app.application.exceptions.api_exceptions import AppError

logger = logging.getLogger(__name__)
router = APIRouter()


class AgentController:
    async def execute_agent(self,
                                       request: AgentRequest,
                                       agent_service: AgentService = Depends(
                                           get_agent_service)) -> AgentResponse:
        try:
            return await agent_service.summarize(request)
        except AppError as e:
            logger.warning("Application error while generating response")
            raise HTTPException(
                status_code=e.status_code,
                detail={
                    "error": e.code,
                    "message": e.message
                },
            )
        except Exception:
            logger.exception("Unexpected error while generating response")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "InternalServerError",
                    "message": "Ha ocurrido un error inesperado al generar la respuesta",
                }
            )


controller = AgentController()
router.post("", response_model=AgentResponse)(controller.execute_agent)

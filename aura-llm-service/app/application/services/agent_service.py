import logging
from typing import List, Optional, Dict, Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from app.application.exceptions.app_exceptions import AppError
from app.application.ollama_configurator.ollama_configurator import OllamaConfigurator
from app.domain.dtos.agent_request import AgentRequest
from app.domain.dtos.agent_response import AgentResponse
from app.domain.dtos.message import Message

logger = logging.getLogger(__name__)


class AgentService:
    SYSTEM_PROMPT: str = (
        "Eres un asistente inteligente que ayuda a los usuarios con documentos. "
        "Tienes acceso a herramientas que te permiten:\n"
        "- Buscar información en documentos usando RAG (execute_rag_tool): Úsala cuando el usuario "
        "haga preguntas sobre el contenido de documentos o necesite información específica.\n"
        "- Generar resúmenes de documentos (execute_summary_tool): Úsala cuando el usuario pida "
        "un resumen, un overview, o quiera entender los puntos principales de un documento.\n\n"
        "Analiza la intención del usuario y decide qué herramienta usar, o si puedes responder "
        "directamente sin herramientas. Siempre proporciona respuestas útiles, claras y en formato Markdown. "
        "Si usas una herramienta, asegúrate de usar la información obtenida para dar una respuesta completa."
    )

    def __init__(self,
                 ollama_configurator: OllamaConfigurator) -> None:
        self.ollama_configurator = ollama_configurator
        self.llm: Runnable = self.ollama_configurator.get_llm_with_tools()
        # Obtener las tools para poder ejecutarlas
        # Asegurarse de que el configurator esté inicializado
        self.ollama_configurator._ensure_initialized()
        self._tools: Dict[str, BaseTool] = {}
        if hasattr(self.ollama_configurator, '_tools') and self.ollama_configurator._tools:
            self._tools = {tool.name: tool for tool in self.ollama_configurator._tools}

    async def execute_agent(self,
                           request: AgentRequest) -> AgentResponse:
        logger.info("Executing agent request")

        try:
            # Construir el input para el LLM
            messages = self._build_llm_input(
                message=request.message,
                messages=request.messages or []
            )

            # Ejecutar el loop de agente (puede invocar tools múltiples veces)
            final_answer, tool_used = await self._agent_loop(messages, max_iterations=5)

            logger.info(f"Agent request executed successfully. Tool used: {tool_used}")

            return AgentResponse(
                answer=final_answer,
                tool_used=tool_used
            )

        except Exception as e:
            logger.exception("Unexpected error during agent execution")
            raise AppError(
                message=f"Error inesperado al ejecutar el agente: {str(e)}",
                status_code=500,
                code="AgentServiceError"
            ) from e

    def _build_llm_input(self,
                       message: str,
                       messages: List[Message]) -> List[BaseMessage]:
        """Construye el input para el LLM con el mensaje y el historial."""
        llm_input: List[BaseMessage] = []

        # Agregar system prompt
        llm_input.append(SystemMessage(content=self.SYSTEM_PROMPT))

        # Agregar historial de conversación
        llm_input.extend(self._build_history_messages(messages))

        # Agregar el mensaje actual
        llm_input.append(HumanMessage(content=message))

        return llm_input

    def _build_history_messages(self,
                               messages: List[Message]) -> List[BaseMessage]:
        """Convierte los mensajes del historial al formato de LangChain."""
        history: List[BaseMessage] = []

        for message in messages:
            if message.role == "user":
                history.append(HumanMessage(content=message.content))
            elif message.role == "assistant":
                history.append(AIMessage(content=message.content))
            else:
                logger.warning(f"Unknown message role: {message.role}, skipping message")

        return history

    async def _invoke_llm(self,
                         llm_input: List[BaseMessage]) -> BaseMessage:
        """Invoca el LLM con el input proporcionado."""
        logger.debug("Invoking LLM with tools")

        try:
            result: BaseMessage = await self.llm.ainvoke(llm_input)

            if not isinstance(result, BaseMessage):
                logger.error("LLM returned invalid type")
                raise AppError(
                    message="LLM retornó un tipo inválido",
                    status_code=500,
                    code="LLMInvalidResponse"
                )

            return result

        except Exception as e:
            logger.error(f"LLM invocation failed: {e}")
            raise AppError(
                message=f"Error al invocar el LLM: {str(e)}",
                status_code=500,
                code="LLMInvocationError"
            ) from e

    async def _agent_loop(self,
                         messages: List[BaseMessage],
                         max_iterations: int = 5) -> tuple[str, Optional[str]]:
        """Ejecuta el loop del agente, manejando tool calls iterativamente."""
        tool_used: Optional[str] = None
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            logger.debug(f"Agent loop iteration {iteration}")

            # Invocar el LLM
            result = await self._invoke_llm(messages)

            # Verificar si hay tool calls
            if isinstance(result, AIMessage) and hasattr(result, 'tool_calls') and result.tool_calls:
                # Agregar la respuesta del LLM al historial
                messages.append(result)

                # Ejecutar las tools
                tool_results = await self._execute_tool_calls(result.tool_calls)
                messages.extend(tool_results)

                # Registrar la primera tool usada
                if tool_used is None and result.tool_calls:
                    first_call = result.tool_calls[0]
                    if isinstance(first_call, dict):
                        tool_used = first_call.get('name')
                    elif hasattr(first_call, 'name'):
                        tool_used = first_call.name

                # Continuar el loop para que el LLM procese los resultados
                continue
            else:
                # No hay tool calls, extraer la respuesta final
                content = result.content
                answer = content if isinstance(content, str) else str(content)
                return answer, tool_used

        # Si llegamos aquí, se alcanzó el máximo de iteraciones
        logger.warning(f"Agent loop reached max iterations ({max_iterations})")
        last_message = messages[-1] if messages else None
        if last_message and isinstance(last_message, AIMessage):
            content = last_message.content
            answer = content if isinstance(content, str) else str(content)
        else:
            answer = "Se alcanzó el límite de iteraciones sin obtener una respuesta final."
        return answer, tool_used

    async def _execute_tool_calls(self,
                                  tool_calls: List[Any]) -> List[ToolMessage]:
        """Ejecuta las tool calls y retorna los resultados como ToolMessages."""
        tool_messages: List[ToolMessage] = []

        for tool_call in tool_calls:
            try:
                # Extraer información del tool call
                if isinstance(tool_call, dict):
                    tool_name = tool_call.get('name')
                    tool_args = tool_call.get('args', {})
                    tool_call_id = tool_call.get('id', '')
                else:
                    tool_name = getattr(tool_call, 'name', None)
                    tool_args = getattr(tool_call, 'args', {})
                    tool_call_id = getattr(tool_call, 'id', '')

                if not tool_name or tool_name not in self._tools:
                    logger.warning(f"Tool {tool_name} not found or not available")
                    tool_messages.append(
                        ToolMessage(
                            content=f"Tool {tool_name} not found",
                            tool_call_id=tool_call_id
                        )
                    )
                    continue

                # Ejecutar la tool
                tool = self._tools[tool_name]
                logger.debug(f"Executing tool: {tool_name} with args: {tool_args}")

                # Las tools de LangChain tienen _arun para ejecución asíncrona
                if hasattr(tool, '_arun'):
                    result = await tool._arun(**tool_args)
                elif hasattr(tool, 'arun'):
                    result = await tool.arun(**tool_args)
                else:
                    result = f"Tool {tool_name} does not support async execution"

                tool_messages.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call_id
                    )
                )

                logger.debug(f"Tool {tool_name} executed successfully")

            except Exception as e:
                logger.error(f"Error executing tool call: {e}")
                tool_call_id = tool_call.get('id', '') if isinstance(tool_call, dict) else getattr(tool_call, 'id', '')
                tool_messages.append(
                    ToolMessage(
                        content=f"Error executing tool: {str(e)}",
                        tool_call_id=tool_call_id
                    )
                )

        return tool_messages


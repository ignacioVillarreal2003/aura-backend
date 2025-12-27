import logging
from typing import Callable, Iterable, List, Optional
from threading import Lock
from urllib.parse import urlparse
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama
from langchain_core.runnables import Runnable

from app.application.exceptions.app_exceptions import ValidationError
from app.application.exceptions.ollama_configurator_exceptions import (
    LLMInitializationError,
    LLMNotConfiguredError,
    ToolInitializationError, LLMInvocationError
)
from app.application.llm_configurator.interfaces.llm_configurator_interface import LLMConfiguratorInterface

logger = logging.getLogger(__name__)

ToolFactory = Callable[[], BaseTool]


class OllamaLLMConfigurator(LLMConfiguratorInterface):
    MIN_TEMPERATURE: float = 0.0
    MAX_TEMPERATURE: float = 1.0

    def __init__(self,
                 *,
                 ollama_model_name: str,
                 ollama_base_url: str,
                 ollama_temperature: float = 0.0,
                 tool_factories: Optional[Iterable[ToolFactory]] = None) -> None:
        self._validate_parameters(
            ollama_model_name=ollama_model_name,
            ollama_base_url=ollama_base_url,
            ollama_temperature=ollama_temperature
        )

        self._ollama_model_name = ollama_model_name.strip()
        self._ollama_base_url = ollama_base_url.strip().rstrip("/")
        self._ollama_temperature = float(ollama_temperature)

        self._tool_factories: List[ToolFactory] = (
            list(tool_factories) if tool_factories else []
        )

        self._initialized: bool = False
        self._init_lock: Lock = Lock()

        self._llm: Optional[Runnable] = None
        self._llm_with_tools: Optional[Runnable] = None
        self._tools_list: List[BaseTool] = []

        logger.debug(
            "OllamaLLMConfigurator initialized",
            extra={
                "model_name": self._ollama_model_name,
                "base_url": self._ollama_base_url,
                "temperature": self._ollama_temperature,
                "tool_factories_count": len(self._tool_factories),
            }
        )

    @staticmethod
    def _validate_parameters(*,
                             ollama_model_name: str,
                             ollama_base_url: str,
                             ollama_temperature: float) -> None:
        if not ollama_model_name or not ollama_model_name.strip():
            raise ValidationError("ollama_model_name cannot be empty", status_code=500)

        if not ollama_base_url or not ollama_base_url.strip():
            raise ValidationError("ollama_base_url cannot be empty", status_code=500)

        try:
            parsed_url = urlparse(ollama_base_url.strip())
            if not parsed_url.scheme or not parsed_url.netloc:
                raise ValidationError("ollama_base_url must be a valid URL", status_code=500)
            if parsed_url.scheme not in ("http", "https"):
                raise ValidationError("ollama_base_url must use http or https scheme", status_code=500)
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError("ollama_base_url is not a valid URL", status_code=500) from e

        if not isinstance(ollama_temperature, (int, float)):
            raise ValidationError("ollama_temperature must be numeric", status_code=500)
        if not (OllamaLLMConfigurator.MIN_TEMPERATURE <= ollama_temperature <= OllamaLLMConfigurator.MAX_TEMPERATURE):
            raise ValidationError(
                f"ollama_temperature must be between {OllamaLLMConfigurator.MIN_TEMPERATURE} and "
                f"{OllamaLLMConfigurator.MAX_TEMPERATURE}",
                status_code=500
            )

    def initialize(self) -> None:
        if self._initialized:
            logger.debug("OllamaLLMConfigurator already initialized")
            return

        with self._init_lock:
            if self._initialized:
                return

            logger.info("Initializing OllamaLLMConfigurator resources")

            try:
                self._initialize_tools()
                self._initialize_base_llm()
                self._bind_tools_to_llm()
                self._initialized = True

                logger.info("OllamaLLMConfigurator initialized successfully")

            except (ToolInitializationError, LLMInitializationError):
                self._cleanup_on_failure()
                raise

            except Exception as e:
                logger.critical(
                    "Failed to initialize OllamaLLMConfigurator",
                    exc_info=True
                )
                self._cleanup_on_failure()
                raise LLMInitializationError("Failed to initialize OllamaLLMConfigurator") from e

    def _cleanup_on_failure(self) -> None:
        self._initialized = False
        self._llm = None
        self._llm_with_tools = None
        self._tools_list = []

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            logger.debug("Lazy-initializing OllamaLLMConfigurator on demand")
            try:
                self.initialize()
            except Exception as e:
                logger.error("Failed to lazy-initialize OllamaLLMConfigurator")
                raise LLMNotConfiguredError("Failed to initialize OllamaLLMConfigurator") from e

    def _initialize_tools(self) -> None:
        if not self._tool_factories:
            logger.debug("No tool factories provided")
            self._tools_list = []
            return

        created_tools: List[BaseTool] = []
        failed_factories: List[int] = []

        for idx, factory in enumerate(self._tool_factories):
            try:
                tool = factory()
                if not isinstance(tool, BaseTool):
                    raise TypeError(f"Factory produced {type(tool).__name__}, expected BaseTool")

                if not hasattr(tool, "args_schema"):
                    logger.warning(f"Tool {getattr(tool, 'name', 'unknown')} missing args_schema")

                created_tools.append(tool)

            except Exception as e:
                logger.warning(f"Tool factory {idx} failed: {e}")
                failed_factories.append(idx)

        self._tools_list = created_tools

        if failed_factories and not created_tools:
            raise ToolInitializationError("All tool factories failed to produce valid tools")

    def _initialize_base_llm(self) -> None:
        try:
            self._llm = ChatOllama(
                model=self._ollama_model_name,
                base_url=self._ollama_base_url,
                temperature=self._ollama_temperature,
            )
        except Exception as e:
            raise LLMInitializationError("Failed to initialize ChatOllama instance") from e

    def _bind_tools_to_llm(self) -> None:
        if self._llm is None:
            raise LLMNotConfiguredError("Base LLM must be initialized before binding tools")

        if not self._tools_list:
            self._llm_with_tools = self._llm
            return

        try:
            self._llm_with_tools = self._llm.bind_tools(self._tools_list)
        except Exception as e:
            logger.warning(f"Failed to bind tools to LLM {e}")
            self._llm_with_tools = self._llm

    async def call_llm(self,
                       llm: Runnable,
                       llm_input: List[BaseMessage]) -> BaseMessage:
        logger.debug("Invoking LLM")

        try:
            response = await llm.ainvoke(llm_input)

            if not isinstance(response, BaseMessage):
                logger.error(
                    "LLM returned an invalid type",
                    extra={
                        "actual_type": type(response).__name__
                    }
                )
                raise LLMInvocationError(
                    f"Expected BaseMessage, but received {type(response).__name__}"
                )

            logger.info("LLM invocation successful")
            return response

        except Exception as e:
            logger.exception(
                "Critical error during LLM invocation",
                extra={
                    "error": str(e)
                }
            )
            raise LLMInvocationError("The LLM failed to process the request") from e

    async def call_llm_text(self,
                            llm: Runnable,
                            llm_input: List[BaseMessage]) -> str:
        response = await self.call_llm(
            llm=llm,
            llm_input=llm_input
        )

        content = getattr(response, "content", None)

        if content is None:
            logger.error(
                "LLM response has no content",
                extra={
                    "response_type": type(response).__name__
                }
            )
            raise LLMInvocationError("LLM response has no content")

        if not isinstance(content, str):
            logger.error(
                "LLM response content is not a string",
                extra={
                    "content_type": type(content).__name__
                }
            )
            raise LLMInvocationError(
                f"Expected response content to be str, got {type(content).__name__}"
            )

        text = content.strip()

        if not text:
            logger.warning("LLM response content is empty after stripping")

        return text

    def get_llm_base(self) -> Runnable:
        self._ensure_initialized()
        if self._llm is None:
            raise LLMNotConfiguredError("Base LLM is not configured")
        return self._llm

    def get_llm_with_tools(self) -> Runnable:
        self._ensure_initialized()
        if self._llm_with_tools is None:
            raise LLMNotConfiguredError("LLM-with-tools is not configured")
        return self._llm_with_tools

    @property
    def tools(self) -> List[BaseTool]:
        return self._tools_list

    @property
    def tool_instructions(self) -> Optional[str]:
        lines = ["Tienes acceso a las siguientes herramientas:"]
        for t in self._tools_list:
            name = getattr(t, "name", getattr(t, "__class__", type(t)).__name__)
            desc = getattr(t, "description", None) or getattr(t, "__doc__", "")
            desc = (desc.strip().split("\n")[0] if desc else "").strip()
            lines.append(f"- {name}: {desc}")
        lines.append("\nUSA estas herramientas cuando sea apropiado para proporcionar respuestas precisas y útiles.")
        return "\n".join(lines)


_global_ollama_llm_configurator: Optional[OllamaLLMConfigurator] = None
_global_ollama_llm_configurator_lock: Lock = Lock()


def get_global_ollama_llm_configurator(*,
                                       ollama_model_name: str,
                                       ollama_base_url: str,
                                       ollama_temperature: float = 0.0,
                                       tool_factories: Optional[List[ToolFactory]] = None) -> OllamaLLMConfigurator:
    global _global_ollama_llm_configurator

    if _global_ollama_llm_configurator:
        return _global_ollama_llm_configurator

    with _global_ollama_llm_configurator_lock:
        if _global_ollama_llm_configurator:
            return _global_ollama_llm_configurator

        _global_ollama_llm_configurator = OllamaLLMConfigurator(
            ollama_model_name=ollama_model_name,
            ollama_base_url=ollama_base_url,
            ollama_temperature=ollama_temperature,
            tool_factories=tool_factories,
        )
        return _global_ollama_llm_configurator

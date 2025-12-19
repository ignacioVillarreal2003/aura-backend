import logging
from typing import Any, Callable, Iterable, List, Optional
from threading import Lock

from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama
from langchain_core.runnables import Runnable

from app.application.exceptions.ollama_configurator_exceptions import (
    LLMInitializationError,
    LLMNotConfiguredError,
)

logger = logging.getLogger(__name__)

ToolFactory = Callable[[], BaseTool]


class OllamaConfigurator:
    MIN_TEMPERATURE: float = 0.0
    MAX_TEMPERATURE: float = 1.0

    def __init__(self,
                 *,
                 ollama_model_name: str,
                 ollama_base_url: str,
                 ollama_temperature: float = 0.0,
                 tool_factories: Optional[Iterable[ToolFactory]] = None) -> None:
        self._validate_parameters(
            ollama_model_name,
            ollama_base_url,
            ollama_temperature
        )

        self._ollama_model_name = ollama_model_name
        self._ollama_base_url = ollama_base_url
        self._ollama_temperature = ollama_temperature

        self._tool_factories: List[ToolFactory] = (
            list(tool_factories) if tool_factories else []
        )

        self._initialized: bool = False
        self._init_lock: Lock = Lock()

        self._llm: Optional[Runnable] = None
        self._llm_with_tools: Optional[Runnable] = None
        self._tools: List[BaseTool] = []

    @staticmethod
    def _validate_parameters(model_name: str,
                             base_url: str,
                             temperature: float) -> None:
        if not model_name or not model_name.strip():
            raise ValueError("ollama_model_name cannot be empty")

        if not base_url or not base_url.strip():
            raise ValueError("ollama_base_url cannot be empty")

        if not isinstance(temperature, (int, float)):
            raise ValueError(f"ollama_temperature must be numeric, got {type(temperature).__name__}")

        if not (OllamaConfigurator.MIN_TEMPERATURE <= temperature <= OllamaConfigurator.MAX_TEMPERATURE):
            raise ValueError(
                f"ollama_temperature must be between {OllamaConfigurator.MIN_TEMPERATURE} "
                f"and {OllamaConfigurator.MAX_TEMPERATURE}, got {temperature}"
            )

    def initialize(self) -> None:
        if self._initialized:
            logger.debug("OllamaConfigurator already initialized")
            return

        with self._init_lock:
            if self._initialized:
                logger.debug("OllamaConfigurator already initialized")
                return

            logger.info("Initializing OllamaConfigurator resources")

            try:
                self._initialize_tools()
                self._initialize_base_llm()
                self._bind_tools_to_llm()
                self._initialized = True

                logger.info("OllamaConfigurator initialized successfully")

            except Exception:
                self._initialized = False
                self._llm = None
                self._llm_with_tools = None
                self._tools = []

                logger.critical("Failed to initialize OllamaConfigurator")
                raise

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            logger.debug("Lazy-initializing OllamaConfigurator on demand")
            self.initialize()

    def _initialize_tools(self) -> None:
        if not self._tool_factories:
            logger.debug("No tool factories provided")
            self._tools = []
            return

        logger.debug(f"Instantiating tools")

        created_tools: List[Any] = []

        for idx, factory in enumerate(self._tool_factories):
            try:
                tool = factory()
                if not hasattr(tool, "args_schema") or not (hasattr(tool, "_arun") or hasattr(tool, "_run")):
                    logger.warning(f"Factory {idx} produced an invalid tool")
                    continue
                created_tools.append(tool)
            except Exception as e:
                logger.warning(f"Tool factory raised an exception: {e}", exc_info=True)

        self._tools = created_tools

        logger.info("Tools initialization completed")

    def _initialize_base_llm(self) -> None:
        logger.debug(f"Creating ChatOllama instance")

        try:
            self._llm = ChatOllama(
                model=self._ollama_model_name,
                base_url=self._ollama_base_url,
                temperature=self._ollama_temperature
            )

            logger.info("Base LLM created successfully")

        except Exception as e:
            logger.critical(f"Failed to initialize ChatOllama instance: {e}")
            raise LLMInitializationError(f"Failed to initialize ChatOllama instance: {e}")

    def _bind_tools_to_llm(self) -> None:
        if self._llm is None:
            raise LLMNotConfiguredError("Base LLM must be initialized before binding tools")

        if not self._tools:
            logger.info("No tools available, using base LLM for both variants")
            self._llm_with_tools = self._llm
            return

        try:
            logger.debug(f"Binding tools to LLM")

            self._llm_with_tools = self._llm.bind_tools(self._tools)

            logger.info("Tools bound to LLM successfully")

        except AttributeError:
            logger.warning("LLM does not support 'bind_tools' method")
            self._llm_with_tools = self._llm

        except Exception as e:
            logger.error(f"Failed to bind tools to LLM: {e}")
            logger.warning("Falling back to base LLM without tools")
            self._llm_with_tools = self._llm

    def get_llm_base(self) -> Runnable:
        try:
            self._ensure_initialized()
        except Exception as e:
            raise LLMNotConfiguredError(f"Failed to initialize base LLM: {e}")

        if self._llm is None:
            raise LLMNotConfiguredError("Base LLM is not configured after initialization")

        logger.debug("Returning base LLM instance")
        return self._llm

    def get_llm_with_tools(self) -> Runnable:
        try:
            self._ensure_initialized()
        except Exception as e:
            raise LLMNotConfiguredError(f"Failed to initialize LLM-with-tools: {e}")

        if self._llm_with_tools is None:
            raise LLMNotConfiguredError("LLM-with-tools is not configured after initialization")

        logger.debug("Returning LLM-with-tools instance")
        return self._llm_with_tools


def create_ollama_configurator(*,
                               ollama_model_name: str,
                               ollama_base_url: str,
                               ollama_temperature: float = 0.0,
                               tool_factories: Optional[Iterable[ToolFactory]] = None) -> OllamaConfigurator:
    return OllamaConfigurator(
        ollama_model_name=ollama_model_name,
        ollama_base_url=ollama_base_url,
        ollama_temperature=ollama_temperature,
        tool_factories=tool_factories,
    )


_global_ollama_configurator: Optional[OllamaConfigurator] = None
_global_ollama_configurator_lock: Lock = Lock()


def get_global_ollama_configurator(*,
                                   ollama_model_name: str,
                                   ollama_base_url: str,
                                   ollama_temperature: float = 0.0,
                                   tool_factories: Optional[List[ToolFactory]] = None) -> OllamaConfigurator:
    global _global_ollama_configurator

    if _global_ollama_configurator is not None:
        logger.debug("Returning existing global OllamaConfigurator instance")
        return _global_ollama_configurator

    with _global_ollama_configurator_lock:
        if _global_ollama_configurator is not None:
            logger.debug("Global OllamaConfigurator created by concurrent thread")
            return _global_ollama_configurator

        logger.debug("Creating global OllamaConfigurator singleton")

        _global_ollama_configurator = create_ollama_configurator(
            ollama_model_name=ollama_model_name,
            ollama_base_url=ollama_base_url,
            ollama_temperature=ollama_temperature,
            tool_factories=tool_factories
        )

        logger.info("Global OllamaConfigurator singleton created")
        return _global_ollama_configurator

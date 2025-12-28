import logging
from typing import Iterable, List, Optional
from asyncio import Lock
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama
from langchain_core.runnables import Runnable

from app.application.llm_facade.exceptions.llm_facade_exceptions import (
    LLMInitializationError,
    LLMNotConfiguredError,
    ToolInitializationError,
    LLMInvocationError
)
from app.application.llm_facade.interfaces.llm_facade_interface import LLMFacadeInterface
from app.application.llm_facade.ollama_configuration import OllamaConfiguration
from app.application.llm_facade.ollama_tool_manager import ToolFactory, OllamaToolManager

logger = logging.getLogger(__name__)


class OllamaLLMFacade(LLMFacadeInterface):
    def __init__(self,
                 *,
                 ollama_model_name: str,
                 ollama_base_url: str,
                 ollama_temperature: float = 0.0,
                 tool_factories: Optional[Iterable[ToolFactory]] = None) -> None:
        self._ollama_configuration = OllamaConfiguration(
            model_name=ollama_model_name,
            base_url=ollama_base_url,
            temperature=ollama_temperature
        )
        self._ollama_tool_manager = OllamaToolManager(tool_factories)

        self._initialized = False
        self._init_lock = Lock()

        self._llm_base: Optional[Runnable] = None
        self._llm_with_tools: Optional[Runnable] = None

        logger.info(
            "OllamaLLMFacade created",
            extra={
                "model_name": self._ollama_configuration.model_name,
                "base_url": self._ollama_configuration.normalized_base_url,
                "temperature": self._ollama_configuration.temperature
            }
        )

    async def initialize(self) -> None:
        async with self._init_lock:
            if self._initialized:
                logger.debug("OllamaLLMFacade already initialized")
                return

            logger.info("Initializing OllamaLLMFacade resources")

            try:
                self._ollama_tool_manager.initialize()
                self._initialize_base_llm()
                self._initialize_llm_with_tools()
                self._initialized = True

                logger.info(
                    "OllamaLLMFacade initialized successfully",
                    extra={
                        "tools_count": len(self._ollama_tool_manager.tools),
                        "has_tool_binding": self._ollama_tool_manager.has_tools
                    }
                )

            except (ToolInitializationError, LLMInitializationError):
                self._cleanup_on_failure()
                raise

            except Exception as e:
                logger.exception("Unexpected error during initialization")
                self._cleanup_on_failure()
                raise LLMInitializationError("Failed to initialize OllamaLLMFacade") from e

    def _initialize_base_llm(self) -> None:
        try:
            self._llm_base = ChatOllama(
                model=self._ollama_configuration.model_name,
                base_url=self._ollama_configuration.normalized_base_url,
                temperature=self._ollama_configuration.temperature,
            )

            logger.debug("Base LLM initialized")

        except Exception as e:
            logger.exception("Failed to create ChatOllama instance")
            raise LLMInitializationError(f"Failed to initialize ChatOllama: {str(e)}") from e

    def _initialize_llm_with_tools(self) -> None:
        if self._llm_base is None:
            raise LLMInitializationError("Base LLM must be initialized before binding tools")

        if not self._ollama_tool_manager.has_tools:
            logger.debug("No tools to bind, using base LLM")
            self._llm_with_tools = self._llm_base
            return

        try:
            self._llm_with_tools = self._llm_base.bind_tools(
                self._ollama_tool_manager.tools
            )

            logger.info(
                f"Tools bound to LLM successfully",
                extra={
                    "tools_count": len(self._ollama_tool_manager.tools)
                }
            )

        except Exception as e:
            logger.warning(
                f"Failed to bind tools to LLM, falling back to base LLM",
                extra={
                    "error": str(e)
                }
            )
            self._llm_with_tools = self._llm_base

    def _cleanup_on_failure(self) -> None:
        logger.debug("Cleaning up after initialization failure")

        self._initialized = False
        self._llm_base = None
        self._llm_with_tools = None

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        logger.debug("Lazy-initializing OllamaLLMFacade on first use")

        try:
            await self.initialize()
        except Exception as e:
            logger.error("Failed to lazy-initialize OllamaLLMFacade")
            raise LLMNotConfiguredError("Failed to initialize OllamaLLMFacade") from e

    @staticmethod
    async def call_llm(llm: Runnable,
                       llm_input: List[BaseMessage]) -> BaseMessage:
        logger.debug(
            "Invoking LLM",
            extra={
                "input_messages_count": len(llm_input)
            }
        )

        try:
            response = await llm.ainvoke(llm_input)

            if not isinstance(response, BaseMessage):
                raise LLMInvocationError(f"Expected BaseMessage, received {type(response).__name__}")

            logger.info("LLM invocation successful")
            return response

        except LLMInvocationError:
            raise

        except Exception as e:
            logger.exception("Critical error during LLM invocation")
            raise LLMInvocationError("The LLM failed to process the request") from e

    async def call_llm_text(self,
                            llm: Runnable,
                            llm_input: List[BaseMessage]) -> str:
        response = await self.call_llm(
            llm=llm,
            llm_input=llm_input)

        return self._extract_text_from_response(response)

    @staticmethod
    def _extract_text_from_response(response: BaseMessage) -> str:
        content = getattr(response, "content", None)

        if content is None:
            raise LLMInvocationError("LLM response has no content attribute")

        if not isinstance(content, str):
            raise LLMInvocationError(f"Expected response content to be str, got {type(content).__name__}")

        text = content.strip()

        if not text:
            logger.warning("LLM response content is empty after stripping")

        return text

    async def get_llm_base(self) -> Runnable:
        await self._ensure_initialized()

        if self._llm_base is None:
            raise LLMNotConfiguredError("Base LLM is not configured")

        return self._llm_base

    async def get_llm_with_tools(self) -> Runnable:
        await self._ensure_initialized()

        if self._llm_with_tools is None:
            raise LLMNotConfiguredError("LLM with tools is not configured")

        return self._llm_with_tools

    @property
    def tools(self) -> List[BaseTool]:
        return self._ollama_tool_manager.tools

    @property
    def tool_instructions(self) -> Optional[str]:
        return self._ollama_tool_manager.generate_instructions()

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def configuration(self) -> OllamaConfiguration:
        return self._ollama_configuration


_global_ollama_llm_facade: Optional[OllamaLLMFacade] = None
_global_ollama_llm_facade_lock = Lock()


async def get_global_ollama_llm_facade(*,
                                       ollama_model_name: str,
                                       ollama_base_url: str,
                                       ollama_temperature: float = 0.0,
                                       tool_factories: Optional[List[ToolFactory]] = None,
                                       auto_initialize: bool = True) -> OllamaLLMFacade:
    global _global_ollama_llm_facade

    async with _global_ollama_llm_facade_lock:
        if _global_ollama_llm_facade is None:
            logger.info("Creating global OllamaLLMFacade")

            _global_ollama_llm_facade = OllamaLLMFacade(
                ollama_model_name=ollama_model_name,
                ollama_base_url=ollama_base_url,
                ollama_temperature=ollama_temperature,
                tool_factories=tool_factories
            )

            if auto_initialize:
                await _global_ollama_llm_facade.initialize()
                logger.info("Global configurator initialized")

        else:
            logger.debug("Returning existing global configurator")

    return _global_ollama_llm_facade


async def reset_global_ollama_llm_facade() -> None:
    global _global_ollama_llm_facade

    async with _global_ollama_llm_facade_lock:
        if _global_ollama_llm_facade is not None:
            logger.info("Resetting global configurator")
            _global_ollama_llm_facade = None

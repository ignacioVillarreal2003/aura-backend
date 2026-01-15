import logging
from typing import Iterable, List, Optional
from asyncio import Lock
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama
from langchain_core.runnables import Runnable

from app.infrastructure.ollama_llm_facade.exceptions.llm_facade_exceptions import (
    LLMInitializationError,
    LLMNotConfiguredError,
    LLMInvocationError
)
from app.infrastructure.ollama_llm_facade.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.ollama_llm_facade.ollama_llm_facade_configuration import OllamaLLMFacadeConfiguration
from app.infrastructure.ollama_llm_facade.ollama_tool_manager import ToolFactory, OllamaToolManager

logger = logging.getLogger(__name__)


class OllamaLLMFacade(OllamaLLMFacadeInterface):
    def __init__(self,
                 *,
                 configuration: OllamaLLMFacadeConfiguration,
                 tool_factories: Optional[Iterable[ToolFactory]] = None) -> None:
        self._configuration = configuration
        self._ollama_tool_manager = OllamaToolManager(tool_factories)

        self._initialized = False
        self._init_lock = Lock()

        self._llm_base: Optional[Runnable] = None
        self._llm_with_tools: Optional[Runnable] = None

        logger.info(
            "OllamaLLMFacade initialized successfully",
            extra={
                "ollama_model_name": self._configuration.ollama_model_name,
                "ollama_base_url": self._configuration.normalized_ollama_base_url,
                "ollama_temperature": self._configuration.ollama_temperature
            }
        )

    @classmethod
    def create(cls,
               ollama_model_name: str,
               ollama_base_url: str,
               ollama_temperature: Optional[float] = None,
               tool_factories: Optional[Iterable[ToolFactory]] = None) -> "OllamaLLMFacade":
        config_kwargs = {}

        if ollama_model_name is not None:
            config_kwargs['ollama_model_name'] = ollama_model_name
        if ollama_base_url is not None:
            config_kwargs['ollama_base_url'] = ollama_base_url
        if ollama_temperature is not None:
            config_kwargs['ollama_temperature'] = ollama_temperature

        configuration = OllamaLLMFacadeConfiguration(**config_kwargs)

        return cls(
            configuration=configuration,
            tool_factories=tool_factories
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
                        "has_tool_binding": self._ollama_tool_manager.has_tools,
                        "ollama_model_name": self._configuration.ollama_model_name
                    }
                )

            except Exception as e:
                logger.exception(
                    "Unexpected error during OllamaLLMFacade initialization",
                    extra={
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }
                )
                self._cleanup_on_failure()
                raise LLMInitializationError("Failed to initialize OllamaLLMFacade") from e

    def _initialize_base_llm(self) -> None:
        try:
            logger.debug(
                "Initializing base LLM",
                extra={
                    "ollama_model_name": self._configuration.ollama_model_name,
                    "ollama_base_url": self._configuration.normalized_ollama_base_url,
                    "ollama_temperature": self._configuration.ollama_temperature
                }
            )

            self._llm_base = ChatOllama(
                model=self._configuration.ollama_model_name,
                base_url=self._configuration.normalized_ollama_base_url,
                temperature=self._configuration.ollama_temperature,
            )

            logger.info(
                "Base LLM initialized successfully",
                extra={
                    "ollama_model_name": self._configuration.ollama_model_name
                }
            )

        except Exception as e:
            logger.error(
                "Failed to create ChatOllama instance",
                extra={
                    "ollama_model_name": self._configuration.ollama_model_name,
                    "ollama_base_url": self._configuration.normalized_ollama_base_url,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise LLMInitializationError(f"Failed to initialize ChatOllama: {str(e)}") from e

    def _initialize_llm_with_tools(self) -> None:
        if self._llm_base is None:
            raise LLMInitializationError("Base LLM must be initialized before binding tools")

        if not self._ollama_tool_manager.has_tools:
            logger.debug("No tools to bind, using base LLM")
            self._llm_with_tools = self._llm_base
            return

        try:
            logger.debug(
                "Binding tools to LLM",
                extra={
                    "tools_count": len(self._ollama_tool_manager.tools)
                }
            )

            self._llm_with_tools = self._llm_base.bind_tools(
                self._ollama_tool_manager.tools
            )

            logger.info(
                "Tools bound to LLM successfully",
                extra={
                    "tools_count": len(self._ollama_tool_manager.tools)
                }
            )

        except Exception as e:
            logger.warning(
                "Failed to bind tools to LLM, falling back to base LLM",
                extra={
                    "tools_count": len(self._ollama_tool_manager.tools),
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
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
            logger.error(
                "Failed to lazy-initialize OllamaLLMFacade",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
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
                logger.error(
                    "LLM returned unexpected response type",
                    extra={
                        "expected_type": "BaseMessage",
                        "received_type": type(response).__name__
                    }
                )
                raise LLMInvocationError(f"Expected BaseMessage, received {type(response).__name__}")

            logger.info(
                "LLM invocation successful",
                extra={
                    "input_messages_count": len(llm_input),
                    "response_type": type(response).__name__
                }
            )
            return response

        except Exception as e:
            logger.exception(
                "Critical error during LLM invocation",
                extra={
                    "input_messages_count": len(llm_input),
                    "error_type": type(e).__name__
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

        return self._extract_text_from_response(response)

    @staticmethod
    def _extract_text_from_response(response: BaseMessage) -> str:
        content = getattr(response, "content", None)

        if content is None:
            logger.error(
                "LLM response has no content attribute",
                extra={
                    "response_type": type(response).__name__
                }
            )
            raise LLMInvocationError("LLM response has no content attribute")

        if not isinstance(content, str):
            logger.error(
                "LLM response content is not a string",
                extra={
                    "expected_type": "str",
                    "received_type": type(content).__name__
                }
            )
            raise LLMInvocationError(
                f"Expected response content to be str, got {type(content).__name__}"
            )

        text = content.strip()

        if not text:
            logger.warning(
                "LLM response content is empty after stripping",
                extra={
                    "original_content_length": len(content) if content else 0
                }
            )

        return text

    async def get_llm_base(self) -> Runnable:
        await self._ensure_initialized()

        if self._llm_base is None:
            logger.error("Base LLM is not configured after initialization")
            raise LLMNotConfiguredError("Base LLM is not configured")

        return self._llm_base

    async def get_llm_with_tools(self) -> Runnable:
        await self._ensure_initialized()

        if self._llm_with_tools is None:
            logger.error("LLM with tools is not configured after initialization")
            raise LLMNotConfiguredError("LLM with tools is not configured")

        return self._llm_with_tools

    @property
    def tools(self) -> List[BaseTool]:
        return self._ollama_tool_manager.tools

    @property
    def tool_instructions(self) -> Optional[str]:
        return self._ollama_tool_manager.generate_instructions()

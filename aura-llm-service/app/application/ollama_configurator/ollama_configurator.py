import asyncio
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
    LLMInvocationError,
    ToolInitializationError
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
        self._tools: List[BaseTool] = []

        logger.debug(
            "OllamaConfigurator initialized",
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
            raise ValidationError(
                "ollama_model_name cannot be empty",
                status_code=500
            )

        if not ollama_base_url or not ollama_base_url.strip():
            raise ValidationError(
                "ollama_base_url cannot be empty",
                status_code=500
            )

        try:
            parsed_url = urlparse(ollama_base_url.strip())
            if not parsed_url.scheme or not parsed_url.netloc:
                raise ValidationError(
                    "ollama_base_url must be a valid URL",
                    status_code=500
                )
            if parsed_url.scheme not in ("http", "https"):
                raise ValidationError(
                    "ollama_base_url must use http or https scheme",
                    status_code=500
                )

        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(
                "ollama_base_url is not a valid URL",
                status_code=500
            ) from e

        if not isinstance(ollama_temperature, (int, float)):
            raise ValidationError(
                "ollama_temperature must be numeric",
                status_code=500
            )

        if not (OllamaConfigurator.MIN_TEMPERATURE <= ollama_temperature <= OllamaConfigurator.MAX_TEMPERATURE):
            raise ValidationError(
                f"ollama_temperature must be between {OllamaConfigurator.MIN_TEMPERATURE} and "
                f"{OllamaConfigurator.MAX_TEMPERATURE}",
                status_code=500
            )

    def initialize(self) -> None:
        if self._initialized:
            logger.debug("OllamaConfigurator already initialized")
            return

        with self._init_lock:
            if self._initialized:
                logger.debug("OllamaConfigurator already initialized")
                return

            logger.info(
                "Initializing OllamaConfigurator resources",
                extra={
                    "model_name": self._ollama_model_name,
                    "base_url": self._ollama_base_url,
                    "tool_factories_count": len(self._tool_factories),
                },
            )

            try:
                self._initialize_tools()
                self._initialize_base_llm()
                self._bind_tools_to_llm()
                self._initialized = True

                logger.info(
                    "OllamaConfigurator initialized successfully",
                    extra={
                        "tools_count": len(self._tools),
                        "model_name": self._ollama_model_name,
                    },
                )

            except (ToolInitializationError, LLMInitializationError):
                self._cleanup_on_failure()
                raise

            except Exception as e:
                logger.critical(
                    "Failed to initialize OllamaConfigurator",
                    extra={
                        "error_type": type(e).__name__
                    },
                    exc_info=True
                )
                self._cleanup_on_failure()
                raise LLMInitializationError("Failed to initialize OllamaConfigurator") from e

    def _cleanup_on_failure(self) -> None:
        self._initialized = False
        self._llm = None
        self._llm_with_tools = None
        self._tools = []

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            logger.debug("Lazy-initializing OllamaConfigurator on demand")
            try:
                self.initialize()
            except Exception as e:
                logger.error(
                    "Failed to lazy-initialize OllamaConfigurator",
                    extra={
                        "error_type": type(e).__name__
                    }
                )
                raise LLMNotConfiguredError("Failed to initialize OllamaConfigurator") from e

    def _initialize_tools(self) -> None:
        if not self._tool_factories:
            logger.debug("No tool factories provided")
            self._tools = []
            return

        logger.debug(
            "Instantiating tools",
            extra={
                "factories_count": len(self._tool_factories)
            }
        )

        created_tools: List[BaseTool] = []
        failed_factories: List[int] = []

        for idx, factory in enumerate(self._tool_factories):
            try:
                tool = factory()

                if not isinstance(tool, BaseTool):
                    logger.warning(
                        "Factory produced non-BaseTool instance",
                        extra={
                            "factory_index": idx,
                            "tool_type": type(tool).__name__
                        }
                    )
                    failed_factories.append(idx)
                    continue

                if not hasattr(tool, "args_schema"):
                    logger.warning(
                        "Tool missing args_schema attribute",
                        extra={
                            "factory_index": idx,
                            "tool_name": getattr(tool, "name", "unknown")
                        }
                    )
                    failed_factories.append(idx)
                    continue

                if not (hasattr(tool, "_arun") or hasattr(tool, "_run")):
                    logger.warning(
                        "Tool missing execution methods",
                        extra={
                            "factory_index": idx,
                            "tool_name": getattr(tool, "name", "unknown")
                        }
                    )
                    failed_factories.append(idx)
                    continue

                created_tools.append(tool)
                logger.debug(
                    "Tool instantiated successfully",
                    extra={
                        "factory_index": idx,
                        "tool_name": getattr(tool, "name", "unknown")
                    }
                )

            except Exception as e:
                logger.warning(
                    "Tool factory raised an exception",
                    extra={
                        "factory_index": idx,
                        "error_type": type(e).__name__
                    },
                    exc_info=True
                )
                failed_factories.append(idx)

        self._tools = created_tools

        if failed_factories and not created_tools:
            raise ToolInitializationError("All tool factories failed to produce valid tools")

        if failed_factories:
            logger.warning(
                "Some tool factories failed",
                extra={
                    "failed_count": len(failed_factories),
                    "successful_count": len(created_tools),
                    "failed_indices": failed_factories
                }
            )

        logger.info(
            "Tools initialization completed",
            extra={
                "tools_count": len(self._tools),
                "failed_factories_count": len(failed_factories)
            }
        )

    def _initialize_base_llm(self) -> None:
        logger.debug(
            "Creating ChatOllama instance",
            extra={
                "model_name": self._ollama_model_name,
                "base_url": self._ollama_base_url,
                "temperature": self._ollama_temperature
            }
        )

        try:
            self._llm = ChatOllama(
                model=self._ollama_model_name,
                base_url=self._ollama_base_url,
                temperature=self._ollama_temperature,
            )

            logger.info(
                "Base LLM created successfully",
                extra={
                    "model_name": self._ollama_model_name
                }
            )

        except Exception as e:
            logger.critical(
                "Failed to initialize ChatOllama instance",
                extra={
                    "model_name": self._ollama_model_name,
                    "base_url": self._ollama_base_url,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise LLMInitializationError("Failed to initialize ChatOllama instance") from e

    def _bind_tools_to_llm(self) -> None:
        if self._llm is None:
            raise LLMNotConfiguredError("Base LLM must be initialized before binding tools")

        if not self._tools:
            logger.info("No tools available, using base LLM for both variants")
            self._llm_with_tools = self._llm
            return

        try:
            logger.debug(
                "Binding tools to LLM",
                extra={
                    "tools_count": len(self._tools)
                }
            )

            self._llm_with_tools = self._llm.bind_tools(self._tools)

            logger.info(
                "Tools bound to LLM successfully",
                extra={
                    "tools_count": len(self._tools)
                }
            )

        except AttributeError:
            logger.warning(
                "LLM does not support 'bind_tools' method, falling back to base LLM",
                extra={
                    "model_name": self._ollama_model_name
                }
            )
            self._llm_with_tools = self._llm

        except Exception as e:
            logger.error(
                "Failed to bind tools to LLM",
                extra={
                    "error_type": type(e).__name__,
                    "tools_count": len(self._tools)
                },
                exc_info=True
            )
            logger.warning("Falling back to base LLM without tools")
            self._llm_with_tools = self._llm

    def get_llm_base(self) -> Runnable:
        try:
            self._ensure_initialized()
        except Exception as e:
            raise LLMNotConfiguredError("Failed to initialize base LLM") from e

        if self._llm is None:
            raise LLMNotConfiguredError("Base LLM is not configured after initialization")

        logger.debug("Returning base LLM instance")
        return self._llm

    def get_llm_with_tools(self) -> Runnable:
        try:
            self._ensure_initialized()
        except Exception as e:
            raise LLMNotConfiguredError("Failed to initialize LLM-with-tools") from e

        if self._llm_with_tools is None:
            raise LLMNotConfiguredError("LLM-with-tools is not configured after initialization")

        logger.debug("Returning LLM-with-tools instance")
        return self._llm_with_tools

    async def _invoke_llm_raw(self,
                              llm: Runnable,
                              llm_input: List[BaseMessage]) -> BaseMessage:
        logger.debug(
            "Invoking LLM",
            extra={
                "messages_count": len(llm_input)
            }
        )

        try:
            if hasattr(llm, "ainvoke"):
                result = await llm.ainvoke(llm_input)
            elif hasattr(llm, "arun"):
                result = await llm.arun(llm_input)
            elif hasattr(llm, "run"):
                result = await asyncio.to_thread(llm.run, llm_input)
            else:
                raise LLMInvocationError("Provided LLM does not expose a known invocation method")

            if not isinstance(result, BaseMessage):
                logger.error(
                    "LLM returned invalid type",
                    extra={
                        "expected_type": "BaseMessage",
                        "actual_type": type(result).__name__
                    }
                )
                raise LLMInvocationError("LLM returned unexpected response type")

            logger.debug("LLM invocation successful")
            return result

        except LLMInvocationError:
            raise

        except Exception as e:
            logger.exception(
                "LLM invocation failed",
                extra={
                    "error_type": type(e).__name__
                }
            )
            raise LLMInvocationError("LLM invocation failed") from e

    @staticmethod
    def _extract_text_from_message(result: BaseMessage) -> str:
        content = getattr(result, "content", None)

        if content is None:
            logger.warning(
                "LLM message has no 'content' attribute",
                extra={
                    "message_type": type(result).__name__
                }
            )
            return str(result)

        if isinstance(content, str):
            return content

        try:
            return str(content)
        except Exception as e:
            logger.warning(
                "Failed to coerce LLM content to string; returning repr()",
                extra={
                    "content_type": type(content).__name__,
                    "error_type": type(e).__name__
                }
            )
            return repr(content)

    async def call_llm(self,
                       llm: Runnable,
                       llm_input: List[BaseMessage]) -> str:
        result = await self._invoke_llm_raw(llm, llm_input)
        return self._extract_text_from_message(result)


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
            tool_factories=tool_factories,
        )

        logger.info(
            "Global OllamaConfigurator singleton created",
            extra={
                "model_name": ollama_model_name,
                "base_url": ollama_base_url
            }
        )

        return _global_ollama_configurator

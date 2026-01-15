import logging
from typing import Optional, Dict, Any, List
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.agent_service.agent_node_configuration import AgentNodeConfiguration
from app.application.services.agent_service.agent_state.agent_state import AgentState
from app.domain.constants.sentimient import Sentiment
from app.infrastructure.ollama_llm_facade.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)


class AgentNode:
    def __init__(self,
                 ollama_llm_facade: OllamaLLMFacadeInterface,
                 configuration: Optional[AgentNodeConfiguration] = None) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._configuration = configuration or AgentNodeConfiguration()

        self._llm_with_tools: Optional[Runnable] = None
        self._llm_initialization_failed = False

        logger.debug("AgentNode initialized")

    async def __call__(self,
                       state: AgentState) -> Dict[str, Any]:
        return await self.process(state)

    async def process(self,
                      state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing agent node")

        await self._ensure_llm_initialized()

        messages = self._extract_messages(state)
        sentiment = self._extract_sentiment(state)

        prompt = self._build_prompt(sentiment, messages)

        logger.debug(
            "Invoking LLM with tools",
            extra={
                "messages_count": len(messages),
                "sentiment": sentiment.value
            }
        )

        try:
            if self._llm_with_tools is None:
                raise RuntimeError("LLM not initialized")

            response = await self._llm_with_tools.ainvoke(prompt)

            if not isinstance(response, BaseMessage):
                raise TypeError(f"LLM returned invalid type: {type(response)}")

            logger.info("Agent node processed successfully")

            return {"messages": [response]}

        except Exception as e:
            logger.exception("LLM invocation failed in agent node")
            raise RuntimeError("Failed to process agent node") from e

    async def _ensure_llm_initialized(self) -> None:
        if self._llm_with_tools is not None:
            return

        if self._llm_initialization_failed:
            raise RuntimeError("LLM initialization failed previously")

        try:
            self._llm_with_tools = await self._ollama_llm_facade.get_llm_with_tools()
            logger.debug("LLM with tools initialized")
        except Exception as e:
            self._llm_initialization_failed = True
            logger.error("Failed to initialize LLM with tools", exc_info=True)
            raise RuntimeError("Failed to initialize LLM for agent") from e

    @staticmethod
    def _extract_messages(state: AgentState) -> List[BaseMessage]:
        messages = state.get("messages")

        if messages is None:
            raise ValueError("State must contain 'messages' field")

        if not isinstance(messages, list):
            raise ValueError(f"Messages must be a list, got {type(messages)}")

        return messages

    @staticmethod
    def _extract_sentiment(state: AgentState) -> Sentiment:
        sentiment = state.get("sentiment", Sentiment.neutral.value)

        try:
            if isinstance(sentiment, str):
                return Sentiment(sentiment)
            elif isinstance(sentiment, Sentiment):
                return sentiment
            else:
                logger.warning(f"Invalid sentiment type: {type(sentiment)}, defaulting to neutral")
                return Sentiment.neutral
        except ValueError:
            logger.warning(f"Invalid sentiment value: {sentiment}, defaulting to neutral")
            return Sentiment.neutral

    def _build_prompt(self,
                      sentiment: Sentiment,
                      messages: List[BaseMessage]) -> List[BaseMessage]:
        prompt_parts = [self._configuration.system_prompt]

        sentiment_instruction = self._configuration.get_sentiment_instruction(sentiment)
        prompt_parts.append(sentiment_instruction)

        if self._ollama_llm_facade.tools:
            tool_instructions = self._ollama_llm_facade.tool_instructions
            if tool_instructions:
                prompt_parts.append(tool_instructions)

        prompt_str = "\n\n".join(prompt_parts)
        system_message = SystemMessage(content=prompt_str)

        return [system_message] + messages

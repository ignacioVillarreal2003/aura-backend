import logging
from typing import Optional, Dict, Any, List
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.agent_service.agent_node.agent_node_configuration import AgentNodeConfiguration
from app.application.services.agent_service.agent_node.agent_node_prompt_builder import AgentNodePromptBuilder
from app.application.services.agent_service.agent_state.agent_state import AgentState
from app.application.services.agent_service.constants.sentimient import Sentiment
from app.infrastructure.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)


class AgentNode:
    def __init__(self,
                 ollama_llm_facade: OllamaLLMFacadeInterface,
                 configuration: Optional[AgentNodeConfiguration] = None) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._configuration = configuration or AgentNodeConfiguration()

        self._prompt_builder = AgentNodePromptBuilder()

        self._llm_with_tools: Optional[Runnable] = None
        self._llm_initialization_failed = False

        logger.debug("AgentNode initialized")

    async def process(self,
                      state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing agent_node node")

        try:
            await self._ensure_llm_initialized()

            messages = self._extract_messages(state)
            sentiment = self._extract_sentiment(state)

            prompt = self._build_prompt(sentiment, messages)

            if self._llm_with_tools is None:
                raise RuntimeError("LLM not initialized")

            response = await self._llm_with_tools.ainvoke(prompt)

            if not isinstance(response, BaseMessage):
                raise TypeError(f"LLM returned invalid type: {type(response)}")

            logger.info("Agent node processed successfully")

            return {
                "messages": [response]
            }

        except Exception as e:
            logger.exception("LLM invocation failed in agent_node node")
            raise RuntimeError("Failed to process agent_node node") from e

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
            raise RuntimeError("Failed to initialize LLM for agent_node") from e

    @staticmethod
    def _extract_messages(agent_state: AgentState) -> List[BaseMessage]:
        messages = agent_state.get("messages")

        if messages is None:
            raise ValueError("AgentState must contain 'messages'")

        if not isinstance(messages, list):
            raise ValueError(f"'messages' must be a list, got {type(messages)}")

        return messages

    @staticmethod
    def _extract_sentiment(agent_state: AgentState) -> Sentiment:
        sentiment = agent_state.get("sentiment", Sentiment.NEUTRAL.value)

        try:
            if isinstance(sentiment, Sentiment):
                return sentiment
            if isinstance(sentiment, str):
                return Sentiment(sentiment)
        except ValueError:
            logger.warning(
                "Invalid sentiment value, defaulting to NEUTRAL"
            )

        return Sentiment.NEUTRAL

    def _build_prompt(self,
                      sentiment: Sentiment,
                      messages: List[BaseMessage]) -> List[BaseMessage]:
        return self._prompt_builder.build_prompt(
            system_prompt=self._configuration.system_prompt,
            sentiment_instruction=self._configuration.get_sentiment_instruction(
                sentiment=sentiment
            ),
            history_messages=messages
        )
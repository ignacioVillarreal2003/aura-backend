from typing import List, Dict, Any, Optional

from langchain_core.messages import SystemMessage, BaseMessage
from langchain_core.runnables import Runnable

from app.application.llm_facade.interfaces.llm_facade_interface import LLMFacadeInterface
from app.application.services.agent_service.agent_node_configuration import AgentNodeConfig
from app.domain.agent_state.agent_state import AgentState
from app.domain.constants.sentimient import Sentiment


class AgentNode:
    def __init__(
            self,
            llm_facade: LLMFacadeInterface,
            config: Optional[AgentNodeConfig] = None
    ):
        self._llm_configurator = llm_facade
        self._config = config or AgentNodeConfig()

        self._llm_with_tools: Optional[Runnable] = None

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        return await self.process(state)

    async def process(self, state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing agent node")

        await self._ensure_llm_initialized()

        messages = self._extract_messages(state)
        sentiment = self._extract_sentiment(state)

        prompt = self._build_prompt(sentiment, messages)

        logger.debug("Invoking LLM with tools")

        try:
            if self._llm_with_tools is None:
                raise RuntimeError("LLM not initialized")

            response = await self._llm_with_tools.ainvoke(prompt)

            if not isinstance(response, BaseMessage):
                raise TypeError(f"LLM returned {type(response)}")

            logger.info("Agent node processed successfully")

            return {"messages": [response]}

        except Exception:
            logger.exception("LLM invocation failed")
            raise

    async def _ensure_llm_initialized(self) -> None:
        if self._llm_with_tools is None:
            self._llm_with_tools = await self._llm_configurator.get_llm_with_tools()

    @staticmethod
    def _extract_messages(state: AgentState) -> List[BaseMessage]:
        messages = state.get("messages")

        if messages is None:
            raise ValueError("State must contain 'messages' field")

        if not isinstance(messages, list):
            raise ValueError("Messages must be a list")

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
                logger.warning(f"Invalid sentiment type: {type(sentiment)}")
                return Sentiment.neutral
        except ValueError:
            logger.warning(f"Invalid sentiment value: {sentiment}")
            return Sentiment.neutral

    def _build_prompt(
            self,
            sentiment: Sentiment,
            messages: List[BaseMessage]
    ) -> List[BaseMessage]:
        prompt_parts = [self._config.base_system_prompt]

        sentiment_instruction = self._config.sentiment_instructions.get(
            sentiment,
            self._config.sentiment_instructions[Sentiment.neutral]
        )
        prompt_parts.append(sentiment_instruction)

        if self._llm_configurator.tools:
            tool_instructions = self._llm_configurator.tool_instructions
            if tool_instructions:
                prompt_parts.append(tool_instructions)

        prompt_str = "\n\n".join(prompt_parts)
        system_message = SystemMessage(content=prompt_str)

        return [system_message] + messages
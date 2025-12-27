import logging
from typing import Dict, Any, List
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.llm_configurator.interfaces.llm_configurator_interface import LLMConfiguratorInterface
from app.application.nodes.interfaces.node_interface import NodeInterface
from app.domain.agent_state.agent_state import AgentState
from app.domain.constants.sentimient import Sentiment

logger = logging.getLogger(__name__)


class AgentNode(NodeInterface):
    BASE_SYSTEM_PROMPT: str = "Eres un asistente inteligente orquestador."
    SENTIMENT_INSTRUCTIONS: Dict[Sentiment, str] = {
        Sentiment.positive: "El usuario está contento. Usa un tono amigable y emojis apropiados. 😊",
        Sentiment.neutral: "El usuario tiene un tono neutral. Mantén un tono profesional y amigable.",
        Sentiment.negative: "El usuario está enojado o frustrado. Sé empático, formal y comprensivo."
    }

    def __init__(self,
                 llm_configurator: LLMConfiguratorInterface):
        self._llm_configurator = llm_configurator
        self._llm_with_tools: Runnable = self._llm_configurator.get_llm_with_tools()

    async def process(self,
                      state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing agent node")

        messages = self._extract_messages(state)
        sentiment = self._extract_sentiment(state)

        prompt = self._build_prompt(sentiment, messages)

        logger.debug("Invoking LLM with tools")

        try:
            response = await self._llm_with_tools.ainvoke(prompt)

            if not isinstance(response, BaseMessage):
                raise TypeError(f"LLM returned {type(response)}")

            logger.info("Agent node processed successfully")
            return {
                "messages": [response]
            }

        except Exception as e:
            logger.error(
                "LLM invocation failed",
                exc_info=True
            )
            raise

    @staticmethod
    def _extract_messages(state: AgentState) -> List[BaseMessage]:
        messages = state.get("messages")
        if messages is None:
            raise ValueError("State must contain 'messages' field")
        if not isinstance(messages, list):
            raise ValueError(f"Messages must be a list")
        return messages

    @staticmethod
    def _extract_sentiment(state: AgentState) -> Sentiment:
        sentiment = state.get("sentiment", Sentiment.neutral)
        try:
            return Sentiment(sentiment)
        except ValueError:
            logger.warning(f"Invalid sentiment value: {sentiment}")
            return Sentiment.neutral

    def _build_prompt(self,
                      sentiment: Sentiment,
                      messages: List[BaseMessage]) -> List[BaseMessage]:
        prompt = [self.BASE_SYSTEM_PROMPT]

        sentiment_instruction = self.SENTIMENT_INSTRUCTIONS.get(
            sentiment,
            self.SENTIMENT_INSTRUCTIONS[Sentiment.neutral]
        )
        prompt.append(sentiment_instruction)

        if self._llm_configurator.tools:
            tool_instructions = getattr(self._llm_configurator, "tool_instructions", None)
            if tool_instructions:
                prompt.append(tool_instructions)

        prompt_str = "\n\n".join(prompt)

        system_message = SystemMessage(
            content=prompt_str
        )

        return [system_message] + messages


def create_agent_node(llm_configurator: LLMConfiguratorInterface) -> AgentNode:
    return AgentNode(llm_configurator)

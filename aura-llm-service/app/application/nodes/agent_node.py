import logging
from typing import Dict, Any, List, Optional
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.ollama_configurator.ollama_configurator import OllamaConfigurator
from app.application.graph.agent_state import AgentState
from app.domain.constants.sentimient import Sentiment

logger = logging.getLogger(__name__)


class AgentNodeConfig:
    def __init__(
            self,
            use_emojis_on_positive: bool = True,
            formal_on_negative: bool = True,
            enable_rag: bool = True,
            enable_summarization: bool = True
    ):
        self.use_emojis_on_positive = use_emojis_on_positive
        self.formal_on_negative = formal_on_negative
        self.enable_rag = enable_rag
        self.enable_summarization = enable_summarization


class AgentNode:
    BASE_SYSTEM_PROMPT: str = "Eres un asistente inteligente orquestador."

    SENTIMENT_INSTRUCTIONS: Dict[Sentiment, str] = {
        Sentiment.positive: "El usuario está contento. Usa un tono amigable y emojis apropiados. 😊",
        Sentiment.neutral: "El usuario tiene un tono neutral. Mantén un tono profesional y amigable.",
        Sentiment.negative: "El usuario está enojado o frustrado. Sé empático, formal y comprensivo."
    }

    TOOL_INSTRUCTIONS: str = (
        "Tienes acceso a las siguientes herramientas:\n"
        "- document_question_tool: Busca información en la base de conocimientos cuando necesites contexto adicional.\n"
        "- document_summary_tool: Resume documentos o textos largos cuando te lo soliciten.\n"
        "\n"
        "USA estas herramientas cuando sea apropiado para proporcionar respuestas precisas y útiles."
    )

    def __init__(self,
                 ollama_configurator: OllamaConfigurator,
                 config: Optional[AgentNodeConfig] = None):
        self.ollama_configurator = ollama_configurator
        self.config = config or AgentNodeConfig()

        self.llm_with_tools: Runnable = self.ollama_configurator.get_llm_with_tools()

        logger.info("AgentNode initialized")

    async def __call__(self,
                       state: AgentState) -> Dict[str, Any]:
        return await self.process(state)

    async def process(self,
                      state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing agent node")

        messages = self._extract_messages(state)
        sentiment = self._extract_sentiment(state)

        logger.debug("State extracted")

        system_prompt = self._build_system_prompt(sentiment)
        full_messages = self._build_full_messages(system_prompt, messages)

        logger.debug("Invoking LLM with tools")

        response = await self._invoke_llm(full_messages)

        logger.info("Agent node processed successfully")

        return {"messages": [response]}

    def _extract_messages(self,
                          state: AgentState) -> List[BaseMessage]:
        messages = state.get("messages")

        if messages is None:
            raise ValueError("State must contain 'messages' field")

        if not isinstance(messages, list):
            raise ValueError(f"Messages must be a list, got {type(messages).__name__}")

        return messages

    def _extract_sentiment(self, state: AgentState) -> Sentiment:
        sentiment_str = state.get("sentiment", "NEUTRAL")

        try:
            return Sentiment(sentiment_str)
        except ValueError:
            logger.warning(f"Invalid sentiment value: {sentiment_str}, defaulting to NEUTRAL")
            return Sentiment.neutral

    def _build_system_prompt(self, sentiment: Sentiment) -> str:
        prompt_parts = [self.BASE_SYSTEM_PROMPT]

        sentiment_instruction = self.SENTIMENT_INSTRUCTIONS.get(
            sentiment,
            self.SENTIMENT_INSTRUCTIONS[Sentiment.neutral]
        )
        prompt_parts.append(sentiment_instruction)

        if self.ollama_configurator._tools > 0:  # No lo tengo
            prompt_parts.append(self.TOOL_INSTRUCTIONS)

        prompt = "\n\n".join(prompt_parts)

        logger.debug("System prompt built")

        return prompt

    def _build_full_messages(self,
                             system_prompt: str,
                             messages: List[BaseMessage]) -> List[BaseMessage]:
        system_message = SystemMessage(content=system_prompt)
        return [system_message] + messages

    async def _invoke_llm(self,
                          messages: List[BaseMessage]) -> BaseMessage:
        try:
            response = await self.llm_with_tools.ainvoke(messages)

            if not isinstance(response, BaseMessage):
                raise TypeError(f"LLM returned invalid type")

            return response

        except Exception:
            logger.error("LLM invocation failed")
            raise


def create_agent_node(ollama_configurator: OllamaConfigurator,
                      config: Optional[AgentNodeConfig] = None) -> AgentNode:
    return AgentNode(ollama_configurator, config)


async def agent_node(state: AgentState,
                     ollama_configurator: OllamaConfigurator) -> Dict[str, Any]:
    node = AgentNode(ollama_configurator)
    return await node(state)

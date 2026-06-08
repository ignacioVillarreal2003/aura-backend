import logging
import re
import unicodedata
from typing import Any, Dict

from app.application.services.user_interactions.agent_service.agent_state.agent_state import AgentState
from app.application.services.user_interactions.agent_service.interfaces.node_interface import NodeInterface

logger = logging.getLogger(__name__)


class InputNormalizerNode(NodeInterface):
    async def process(self, agent_state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing input normalizer")

        messages = agent_state.get("messages", [])
        if not messages:
            logger.warning("No messages in state — returning empty query")
            return {"normalized_query": ""}

        last_message = messages[-1]
        raw_content = (
            last_message.content
            if hasattr(last_message, "content")
            else str(last_message)
        )

        normalized = self._normalize(raw_content)

        logger.info(
            "Input normalized",
            extra={"original_length": len(raw_content), "normalized_length": len(normalized)},
        )
        return {"normalized_query": normalized}

    @staticmethod
    def _normalize(text: str) -> str:
        text = unicodedata.normalize("NFC", text)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

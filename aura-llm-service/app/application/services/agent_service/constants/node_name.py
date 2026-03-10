import logging
from enum import Enum

logger = logging.getLogger(__name__)


class NodeName(str, Enum):
    SENTIMENT = "sentiment_node"
    AGENT = "agent_node"
    TOOLS = "tools"

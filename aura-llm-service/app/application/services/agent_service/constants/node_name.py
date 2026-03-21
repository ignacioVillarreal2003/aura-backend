from enum import Enum


class NodeName(str, Enum):
    sentiment_node = "sentiment_node"
    agent_node = "agent_node"
    tools = "tools"

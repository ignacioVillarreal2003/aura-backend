from enum import Enum


class MessageRole(str, Enum):
    system = "system"
    user = "user"
    human = "human"
    assistant = "assistant"
    ai = "ai"
    tool = "tool"
    function = "function"

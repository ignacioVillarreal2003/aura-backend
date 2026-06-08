from enum import Enum


class MessageRole(str, Enum):
    human = "human"
    assistant = "assistant"

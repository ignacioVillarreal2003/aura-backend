import logging
from typing import List
from langchain_core.messages import BaseMessage


def truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"... [+{len(text) - max_chars} chars]"


def log_llm_input(logger: logging.Logger, llm_input: List[BaseMessage], max_chars: int) -> None:
    for index, message in enumerate(llm_input):
        content = message.content if isinstance(message.content, str) else str(message.content)
        logger.debug(
            "LLM input message",
            extra={
                "message_index": index,
                "message_role": message.type,
                "message_chars": len(content),
                "message_content": truncate(content, max_chars),
            },
        )


def log_llm_output(logger: logging.Logger, content: str, max_chars: int) -> None:
    logger.debug(
        "LLM output message",
        extra={
            "message_chars": len(content),
            "message_content": truncate(content, max_chars),
        },
    )

from typing import Protocol


class LLMServiceInterface(Protocol):
    async def call(self,
                   messages: list[dict]) -> dict:
        ...

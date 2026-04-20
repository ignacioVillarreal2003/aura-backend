from abc import ABC, abstractmethod


class ContentDeduplicationPortInterface(ABC):
    @abstractmethod
    async def try_claim_content_hash(
            self,
            file_hash: str,
            window_seconds: int,
    ) -> bool:
        pass

    @abstractmethod
    async def release_content_hash_claim(
            self,
            file_hash: str,
    ) -> None:
        pass

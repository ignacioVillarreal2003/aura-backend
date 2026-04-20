from abc import ABC, abstractmethod


class PostProcessDocumentJobPublisherInterface(ABC):
    @abstractmethod
    async def publish_job(
            self,
            job_id: str,
    ) -> str:
        pass

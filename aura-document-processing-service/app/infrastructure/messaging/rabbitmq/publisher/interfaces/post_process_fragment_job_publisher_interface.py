from abc import ABC, abstractmethod


class PostProcessFragmentJobPublisherInterface(ABC):
    @abstractmethod
    async def publish_job(
            self,
            job_id: str,
    ) -> str:
        pass

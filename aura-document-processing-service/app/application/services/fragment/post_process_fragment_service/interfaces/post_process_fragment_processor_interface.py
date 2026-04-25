from abc import ABC, abstractmethod


class PostProcessFragmentProcessorInterface(ABC):
    @abstractmethod
    async def run_job(
            self,
            job_id: str,
    ) -> None:
        pass

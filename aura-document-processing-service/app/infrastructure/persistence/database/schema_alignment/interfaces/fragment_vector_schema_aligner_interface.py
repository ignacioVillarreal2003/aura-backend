from abc import ABC, abstractmethod


class FragmentVectorSchemaAlignerInterface(ABC):
    @abstractmethod
    async def align_to_active_dimension(self) -> bool:
        pass

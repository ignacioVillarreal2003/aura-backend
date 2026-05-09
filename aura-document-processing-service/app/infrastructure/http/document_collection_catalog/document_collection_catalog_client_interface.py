from abc import ABC, abstractmethod


class DocumentCollectionCatalogClientInterface(ABC):
    """Fetches MAC-derived accessible collection identifiers from document-collection-service."""

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    async def fetch_all_accessible_collection_ids(
            self,
            *,
            user_id: int,
            authorization_header: str | None,
    ) -> frozenset[int]:
        pass

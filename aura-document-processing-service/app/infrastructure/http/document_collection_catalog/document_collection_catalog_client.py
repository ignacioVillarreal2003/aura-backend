import logging
from typing import Any, Optional
import httpx

from app.infrastructure.http.document_collection_catalog.document_collection_catalog_client_interface import (
    DocumentCollectionCatalogClientInterface,
)
from app.infrastructure.http.document_collection_catalog.document_collection_catalog_settings import (
    DocumentCollectionCatalogSettings,
)
from app.infrastructure.http.http_client.http_client_exceptions import HttpClientException
from app.infrastructure.http.http_client.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)


class DocumentCollectionCatalogClient(DocumentCollectionCatalogClientInterface):
    def __init__(
            self,
            http_client: HttpClientInterface,
            settings: Optional[DocumentCollectionCatalogSettings] = None,
    ) -> None:
        self._http_client = http_client
        self._settings = settings or DocumentCollectionCatalogSettings()

    async def fetch_all_accessible_collection_ids(
            self,
            *,
            user_id: int,
            authorization_header: str | None,
    ) -> frozenset[int]:
        bearer = self._normalize_bearer(authorization_header or self._settings.fallback_bearer_token)
        if bearer is None:
            logger.debug(
                "Skipping accessible-collections fetch: no bearer token.",
                extra={"user_id": user_id},
            )
            return frozenset()

        url = f"{self._settings.accessible_collections_url.rstrip('/')}/{user_id}/accessible-collections/"
        ids: set[int] = set()
        pages_read = 0
        headers = {
            "Authorization": bearer,
            "Accept": "application/json",
        }
        timeout = self._settings.request_timeout_seconds

        try:
            while url and pages_read < self._settings.max_pages:
                if pages_read == 0:
                    response = await self._http_client.get(
                        url,
                        headers=headers,
                        params={"page_size": self._settings.page_size},
                        timeout=timeout,
                    )
                else:
                    response = await self._http_client.get(
                        url,
                        headers=headers,
                        timeout=timeout,
                    )
                pages_read += 1
                if response.status_code >= 400:
                    logger.warning(
                        "Accessible collections request failed.",
                        extra={
                            "user_id": user_id,
                            "status_code": response.status_code,
                        },
                    )
                    return frozenset()

                payload_any: Any = response.json()
                if not isinstance(payload_any, dict):
                    logger.warning(
                        "Unexpected accessible-collections payload shape.",
                        extra={"user_id": user_id},
                    )
                    return frozenset()

                payload = payload_any
                results = payload.get("results")
                if isinstance(results, list):
                    for row in results:
                        if isinstance(row, dict):
                            cid = row.get("id")
                            if isinstance(cid, int):
                                ids.add(cid)
                            elif isinstance(cid, str) and cid.isdigit():
                                ids.add(int(cid))

                nxt = payload.get("next")
                if isinstance(nxt, str) and nxt.strip():
                    url = nxt.strip()
                else:
                    url = ""

            if pages_read >= self._settings.max_pages:
                logger.warning(
                    "Stopped paginating accessible-collections after max_pages.",
                    extra={"user_id": user_id, "max_pages": self._settings.max_pages},
                )

        except (HttpClientException, httpx.RequestError):
            logger.exception(
                "Error while fetching accessible collections.",
                extra={"user_id": user_id},
            )
            return frozenset()
        except ValueError:
            logger.exception(
                "Invalid JSON while fetching accessible collections.",
                extra={"user_id": user_id},
            )
            return frozenset()

        return frozenset(ids)

    @staticmethod
    def _normalize_bearer(raw: Optional[str]) -> Optional[str]:
        if raw is None:
            return None
        stripped = raw.strip()
        if not stripped:
            return None
        if stripped.lower().startswith("bearer "):
            return stripped
        return f"Bearer {stripped}"

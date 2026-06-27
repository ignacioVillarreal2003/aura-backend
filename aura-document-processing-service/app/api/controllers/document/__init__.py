from app.api.controllers.document.create_document_controller.create_document_controller import (
    router as create_document_router,
)
from app.api.controllers.document.bulk_create_document_controller.bulk_create_document_controller import (
    router as bulk_create_document_router,
)
from app.api.controllers.document.delete_document_controller.delete_document_controller import (
    router as delete_document_router,
)
from app.api.controllers.document.document_download_controller.document_download_controller import (
    router as document_download_router,
)
from app.api.controllers.document.document_query_controller.document_query_controller import (
    router as document_query_router,
)
from app.api.controllers.document.document_search_controller.document_search_controller import (
    router as document_search_router,
)
from app.api.controllers.document.document_reembed_controller.document_reembed_controller import (
    router as document_reembed_router,
)
from app.api.controllers.document.document_reprocess_controller.document_reprocess_controller import (
    router as document_reprocess_router,
)
from app.api.controllers.document.document_enrich_controller.document_enrich_controller import (
    router as document_enrich_router,
)
from app.api.controllers.document.update_document_controller.update_document_controller import (
    router as update_document_router,
)
from app.api.controllers.document.restore_document_controller.restore_document_controller import (
    router as restore_document_router,
)

__all__ = [
    "bulk_create_document_router",
    "create_document_router",
    "delete_document_router",
    "document_download_router",
    "document_enrich_router",
    "document_query_router",
    "document_reembed_router",
    "document_reprocess_router",
    "document_search_router",
    "restore_document_router",
    "update_document_router",
]

from app.api.controllers.document.create_document.create_document_controller import (
    router as create_document_router,
)
from app.api.controllers.document.delete_document.delete_document_controller import (
    router as delete_document_router,
)
from app.api.controllers.document.document_download.document_download_controller import (
    router as document_download_router,
)
from app.api.controllers.document.document_query.document_query_controller import (
    router as document_query_router,
)
from app.api.controllers.document.post_process_document.post_process_document_controller import (
    router as post_process_document_router,
)

__all__ = [
    "create_document_router",
    "delete_document_router",
    "document_download_router",
    "document_query_router",
    "post_process_document_router",
]

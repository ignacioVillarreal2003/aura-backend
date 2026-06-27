import logging
from fastapi import HTTPException, Request, status

from app.application.services.document.create_document_service.interfaces.create_document_service_interface import (
    CreateDocumentServiceInterface,
)
from app.application.services.document.delete_document_service.interfaces.delete_document_service_interface import (
    DeleteDocumentServiceInterface,
)
from app.application.services.document.document_download_service.interfaces.document_download_service_interface import (
    DocumentDownloadServiceInterface,
)
from app.application.services.document.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface,
)
from app.application.services.document.bulk_create_document_service.interfaces.bulk_create_document_service_interface import (
    BulkCreateDocumentServiceInterface,
)
from app.application.services.document.bulk_dispatch_service.interfaces.bulk_dispatch_service_interface import (
    BulkDispatchServiceInterface,
)
from app.application.services.document.document_search_service.interfaces.document_search_service_interface import (
    DocumentSearchServiceInterface,
)
from app.application.services.document.update_document_service.interfaces.update_document_service_interface import (
    UpdateDocumentServiceInterface,
)
from app.application.services.document.restore_document_service.interfaces.restore_document_service_interface import (
    RestoreDocumentServiceInterface,
)
from app.application.services.fragment.fragment_query_service.interfaces.fragment_query_service_interface import (
    FragmentQueryServiceInterface,
)
from app.application.services.graph.graph_context_service.interfaces.graph_context_service_interface import (
    GraphContextServiceInterface,
)
from app.application.services.graph.graph_entity_service.interfaces.graph_entity_service_interface import (
    GraphEntityServiceInterface,
)
from app.application.services.graph.graph_ontology_service.interfaces.graph_ontology_service_interface import (
    GraphOntologyServiceInterface,
)
from app.application.services.graph.graph_path_service.interfaces.graph_path_service_interface import (
    GraphPathServiceInterface,
)
from app.application.services.graph.graph_query_service.interfaces.graph_query_service_interface import (
    GraphQueryServiceInterface,
)
from app.application.services.graph.graph_stats_service.interfaces.graph_stats_service_interface import (
    GraphStatsServiceInterface,
)

logger = logging.getLogger(__name__)

_503 = status.HTTP_503_SERVICE_UNAVAILABLE


def _unavailable(name: str) -> HTTPException:
    logger.error("Service not registered on application state.", extra={"service": name})
    return HTTPException(status_code=_503, detail=f"{name} is not available.")


async def get_create_document_service(request: Request) -> CreateDocumentServiceInterface:
    svc = getattr(request.app.state, "create_document_service", None)
    if svc is None:
        raise _unavailable("CreateDocumentService")
    return svc


async def get_delete_document_service(request: Request) -> DeleteDocumentServiceInterface:
    svc = getattr(request.app.state, "delete_document_service", None)
    if svc is None:
        raise _unavailable("DeleteDocumentService")
    return svc


async def get_document_download_service(request: Request) -> DocumentDownloadServiceInterface:
    svc = getattr(request.app.state, "document_download_service", None)
    if svc is None:
        raise _unavailable("DocumentDownloadService")
    return svc


async def get_document_query_service(request: Request) -> DocumentQueryServiceInterface:
    svc = getattr(request.app.state, "document_query_service", None)
    if svc is None:
        raise _unavailable("DocumentQueryService")
    return svc


async def get_document_search_service(request: Request) -> DocumentSearchServiceInterface:
    svc = getattr(request.app.state, "document_search_service", None)
    if svc is None:
        raise _unavailable("DocumentSearchService")
    return svc


async def get_update_document_service(request: Request) -> UpdateDocumentServiceInterface:
    svc = getattr(request.app.state, "update_document_service", None)
    if svc is None:
        raise _unavailable("UpdateDocumentService")
    return svc


async def get_restore_document_service(request: Request) -> RestoreDocumentServiceInterface:
    svc = getattr(request.app.state, "restore_document_service", None)
    if svc is None:
        raise _unavailable("RestoreDocumentService")
    return svc


async def get_bulk_create_document_service(request: Request) -> BulkCreateDocumentServiceInterface:
    svc = getattr(request.app.state, "bulk_create_document_service", None)
    if svc is None:
        raise _unavailable("BulkCreateDocumentService")
    return svc


async def get_bulk_dispatch_service(request: Request) -> BulkDispatchServiceInterface:
    svc = getattr(request.app.state, "bulk_dispatch_service", None)
    if svc is None:
        raise _unavailable("BulkDispatchService")
    return svc


async def get_fragment_query_service(request: Request) -> FragmentQueryServiceInterface:
    svc = getattr(request.app.state, "fragment_query_service", None)
    if svc is None:
        raise _unavailable("FragmentQueryService")
    return svc


async def get_graph_context_service(request: Request) -> GraphContextServiceInterface:
    svc = getattr(request.app.state, "graph_context_service", None)
    if svc is None:
        raise _unavailable("GraphContextService")
    return svc


async def get_graph_entity_service(request: Request) -> GraphEntityServiceInterface:
    svc = getattr(request.app.state, "graph_entity_service", None)
    if svc is None:
        raise _unavailable("GraphEntityService")
    return svc


async def get_graph_ontology_service(request: Request) -> GraphOntologyServiceInterface:
    svc = getattr(request.app.state, "graph_ontology_service", None)
    if svc is None:
        raise _unavailable("GraphOntologyService")
    return svc


async def get_graph_path_service(request: Request) -> GraphPathServiceInterface:
    svc = getattr(request.app.state, "graph_path_service", None)
    if svc is None:
        raise _unavailable("GraphPathService")
    return svc


async def get_graph_query_service(request: Request) -> GraphQueryServiceInterface:
    svc = getattr(request.app.state, "graph_query_service", None)
    if svc is None:
        raise _unavailable("GraphQueryService")
    return svc


async def get_graph_stats_service(request: Request) -> GraphStatsServiceInterface:
    svc = getattr(request.app.state, "graph_stats_service", None)
    if svc is None:
        raise _unavailable("GraphStatsService")
    return svc

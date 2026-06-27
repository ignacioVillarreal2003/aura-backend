from fastapi import APIRouter

from app.api.controllers.fragment import (
    fragment_query_router,
)
from app.api.controllers.document import (
    bulk_create_document_router,
    create_document_router,
    delete_document_router,
    document_download_router,
    document_query_router,
    document_search_router,
    document_reembed_router,
    document_reprocess_router,
    document_enrich_router,
    update_document_router,
    restore_document_router,
)
from app.api.controllers.graph import (
    graph_context_router,
    graph_entity_router,
    graph_extraction_router,
    graph_ontology_router,
    graph_path_router,
    graph_query_router,
    graph_search_router,
    graph_stats_router,
)
from app.api.controllers.health_controller import health_controller

router = APIRouter()

router.include_router(
    health_controller.router,
    tags=["health"],
)

router.include_router(
    delete_document_router,
    prefix="/delete-document",
    tags=["delete-document"],
)

router.include_router(
    create_document_router,
    prefix="/create-document",
    tags=["create-document"],
)

router.include_router(
    bulk_create_document_router,
    prefix="/bulk-create-document",
    tags=["bulk-create-document"],
)

router.include_router(
    update_document_router,
    prefix="/update-document",
    tags=["update-document"],
)

router.include_router(
    restore_document_router,
    prefix="/restore-document",
    tags=["restore-document"],
)

router.include_router(
    document_query_router,
    prefix="/document-query",
    tags=["document-query"],
)

router.include_router(
    document_download_router,
    prefix="/document-download",
    tags=["document-download"],
)

router.include_router(
    document_search_router,
    prefix="/document-search",
    tags=["document-search"],
)

router.include_router(
    document_reembed_router,
    prefix="/document-reembed",
    tags=["document-reembed"],
)

router.include_router(
    document_reprocess_router,
    prefix="/document-reprocess",
    tags=["document-reprocess"],
)

router.include_router(
    document_enrich_router,
    prefix="/document-enrich",
    tags=["document-enrich"],
)

router.include_router(
    fragment_query_router,
    prefix="/fragment-query",
    tags=["fragment-query"],
)

router.include_router(
    graph_query_router,
    prefix="/graph/query",
    tags=["graph-query"],
)

router.include_router(
    graph_context_router,
    prefix="/graph/context",
    tags=["graph-context"],
)

router.include_router(
    graph_entity_router,
    prefix="/graph/entity",
    tags=["graph-entity"],
)

router.include_router(
    graph_path_router,
    prefix="/graph/path",
    tags=["graph-path"],
)

router.include_router(
    graph_extraction_router,
    prefix="/graph/extraction",
    tags=["graph-extraction"],
)

router.include_router(
    graph_search_router,
    prefix="/graph/search",
    tags=["graph-search"],
)

router.include_router(
    graph_ontology_router,
    prefix="/graph/ontology",
    tags=["graph-ontology"],
)

router.include_router(
    graph_stats_router,
    prefix="/graph/stats",
    tags=["graph-stats"],
)

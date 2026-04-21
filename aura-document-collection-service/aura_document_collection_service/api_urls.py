from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers as nested_routers

from apps.document_collection_documents.views import DocumentCollectionDocumentViewSet
from apps.document_collection_users.views import DocumentCollectionUserViewSet
from apps.document_collections.views import DocumentCollectionViewSet

router = DefaultRouter()
router.register("document-collections", DocumentCollectionViewSet, basename="document-collection")

nested = nested_routers.NestedSimpleRouter(router, r"document-collections", lookup="document_collection")
nested.register(r"users", DocumentCollectionUserViewSet, basename="document-collection-user")
nested.register(r"documents", DocumentCollectionDocumentViewSet, basename="document-collection-document")

urlpatterns = [
    path("", include(router.urls)),
    path("", include(nested.urls)),
]

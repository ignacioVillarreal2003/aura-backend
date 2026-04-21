from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter

from apps.document_collection_documents.views import DocumentCollectionDocumentViewSet
from apps.document_collection_users.views import DocumentCollectionUserViewSet
from apps.document_collections.views import DocumentCollectionViewSet

router = DefaultRouter()
router.register("document-collections", DocumentCollectionViewSet, basename="document-collection")

_POSITIVE_INT = r"[1-9][0-9]*"

document_collection_users = DocumentCollectionUserViewSet.as_view({"get": "list", "post": "create"})
document_collection_user_destroy = DocumentCollectionUserViewSet.as_view({"delete": "destroy"})
document_collection_documents = DocumentCollectionDocumentViewSet.as_view({"get": "list", "post": "create"})
document_collection_document_destroy = DocumentCollectionDocumentViewSet.as_view({"delete": "destroy"})

urlpatterns = [
    path("", include(router.urls)),
    re_path(
        rf"^document-collections/(?P<document_collection_id>{_POSITIVE_INT})/users/(?P<user_id>{_POSITIVE_INT})/$",
        document_collection_user_destroy,
        name="document-collection-user-destroy",
    ),
    re_path(
        rf"^document-collections/(?P<document_collection_id>{_POSITIVE_INT})/users/$",
        document_collection_users,
        name="document-collection-users-list",
    ),
    re_path(
        rf"^document-collections/(?P<document_collection_id>{_POSITIVE_INT})/documents/(?P<document_id>{_POSITIVE_INT})/$",
        document_collection_document_destroy,
        name="document-collection-document-destroy",
    ),
    re_path(
        rf"^document-collections/(?P<document_collection_id>{_POSITIVE_INT})/documents/$",
        document_collection_documents,
        name="document-collection-documents-list",
    ),
]

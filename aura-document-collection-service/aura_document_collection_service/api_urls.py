from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers as nested_routers

from apps.classification_levels.views import ClassificationLevelViewSet
from apps.compartments.views import CompartmentViewSet
from apps.document_collection_documents.views import DocumentCollectionDocumentViewSet
from apps.document_collections.views import DocumentCollectionViewSet
from apps.user_authorizations.views import UserAuthorizationViewSet

router = DefaultRouter()
router.register("document-collections", DocumentCollectionViewSet, basename="document-collection")
router.register("classification-levels", ClassificationLevelViewSet, basename="classification-level")
router.register("compartments", CompartmentViewSet, basename="compartment")
router.register("user-authorizations", UserAuthorizationViewSet, basename="user-authorization")

nested = nested_routers.NestedSimpleRouter(router, r"document-collections", lookup="document_collection")
nested.register(r"documents", DocumentCollectionDocumentViewSet, basename="document-collection-document")

urlpatterns = [
    path("", include(router.urls)),
    path("", include(nested.urls)),
]

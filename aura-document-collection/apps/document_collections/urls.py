from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.document_collections.views import DocumentCollectionViewSet

router = DefaultRouter()
router.register("document-collections", DocumentCollectionViewSet, basename="document-collection")

urlpatterns = [
    path("", include(router.urls)),
]

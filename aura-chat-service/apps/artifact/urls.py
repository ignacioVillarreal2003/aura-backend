from django.urls import path

from apps.artifact.views import (
    ArtifactDetailView,
    ArtifactListView,
    ArtifactManageView,
    ArtifactVersionsView,
)

urlpatterns = [
    path("", ArtifactListView.as_view(), name="artifact-list"),
    path("manage/", ArtifactManageView.as_view(), name="artifact-manage"),
    path("<int:artifact_id>/", ArtifactDetailView.as_view(), name="artifact-detail"),
    path("<int:artifact_id>/versions/", ArtifactVersionsView.as_view(), name="artifact-versions"),
]

from django.urls import path

from apps.artifact.interaction_views import (
    ArtifactBookmarkView,
    ArtifactFeedbackView,
    ArtifactPinView,
    ArtifactThreadReplyDetailView,
    ArtifactThreadView,
    BookmarkedArtifactListView,
    FeedbackAnalyticsView,
    PinnedArtifactListView,
)
from apps.artifact.views import (
    ArtifactDetailView,
    ChatArtifactFeedView,
    ChatArtifactManageView,
)

urlpatterns = [
    path("chats/<int:chat_id>/", ChatArtifactFeedView.as_view(), name="artifact-chat-feed"),
    path("chats/<int:chat_id>/manage/", ChatArtifactManageView.as_view(), name="artifact-chat-manage"),
    path("pinned/", PinnedArtifactListView.as_view(), name="artifact-pinned-list"),
    path("bookmarked/", BookmarkedArtifactListView.as_view(), name="artifact-bookmarked-list"),
    path("feedback/analytics/", FeedbackAnalyticsView.as_view(), name="artifact-feedback-analytics"),
    path("<int:artifact_id>/", ArtifactDetailView.as_view(), name="artifact-detail"),
    path("<int:artifact_id>/feedback/", ArtifactFeedbackView.as_view(), name="artifact-feedback"),
    path("<int:artifact_id>/bookmark/", ArtifactBookmarkView.as_view(), name="artifact-bookmark"),
    path("<int:artifact_id>/pin/", ArtifactPinView.as_view(), name="artifact-pin"),
    path("<int:artifact_id>/thread/", ArtifactThreadView.as_view(), name="artifact-thread"),
    path("<int:artifact_id>/thread/<int:reply_id>/", ArtifactThreadReplyDetailView.as_view(), name="artifact-thread-reply-detail"),
]

from django.urls import path

from apps.membership.views.membership_view import (
    LeaveChatView,
    MemberDetailView,
    MemberListView,
)

urlpatterns = [
    path("", MemberListView.as_view(), name="member-list"),
    path("<int:member_id>/", MemberDetailView.as_view(), name="member-detail"),
    path("leave/", LeaveChatView.as_view(), name="leave-chat"),
]

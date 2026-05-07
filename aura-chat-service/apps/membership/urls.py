from django.urls import path

from apps.membership.views.membership_view import (
    LeaveChatView,
    MemberDetailView,
    MemberListView,
)
from apps.membership.views.role_view import RoleUpdateView

urlpatterns = [
    path("", MemberListView.as_view(), name="member-list"),
    path("<int:member_id>/", MemberDetailView.as_view(), name="member-detail"),
    path("<int:member_id>/role/", RoleUpdateView.as_view(), name="member-role"),
    path("leave/", LeaveChatView.as_view(), name="leave-chat"),
]

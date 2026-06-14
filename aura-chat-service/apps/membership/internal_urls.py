from django.urls import path

from apps.membership.views.internal_membership_view import InternalChatMembershipView

urlpatterns = [
    path(
        "<int:user_id>/",
        InternalChatMembershipView.as_view(),
        name="internal-membership-check",
    ),
]

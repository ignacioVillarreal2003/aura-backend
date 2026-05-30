from django.urls import path

from apps.membership.views.membership_view import MyMembershipsView

urlpatterns = [
    path("", MyMembershipsView.as_view(), name="my-memberships"),
]

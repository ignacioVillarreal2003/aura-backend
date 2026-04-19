"""Auth API URL routes."""

from django.urls import path
from accounts.api.views import LoginView, RefreshView, LogoutView, ValidateView, UserBulkLookupView

urlpatterns = [
    path('login', LoginView.as_view(), name='auth-login'),
    path('refresh', RefreshView.as_view(), name='auth-refresh'),
    path('logout', LogoutView.as_view(), name='auth-logout'),
    path('validate', ValidateView.as_view(), name='auth-validate'),
    path('bulk-lookup', UserBulkLookupView.as_view(), name='auth-users-bulk-lookup'),
]

"""Auth API URL routes."""

from django.urls import path
from accounts.api.views import (
    LoginView, RefreshView, LogoutView, ValidateView,
    UserLookupView, ChangePasswordView,
)

urlpatterns = [
    path('login', LoginView.as_view(), name='auth-login'),
    path('refresh', RefreshView.as_view(), name='auth-refresh'),
    path('logout', LogoutView.as_view(), name='auth-logout'),
    path('validate', ValidateView.as_view(), name='auth-validate'),
    path('users/lookup', UserLookupView.as_view(), name='auth-user-lookup'),
    path('change-password', ChangePasswordView.as_view(), name='auth-change-password'),
]

"""Rutas de la API de autenticacion."""

from django.urls import path
from apps.accounts.api.views import (
    LoginView, RefreshView, LogoutView, ValidateView,
    UserLookupView, UsersByIdsView, ChangePasswordView,
)

urlpatterns = [
    path('login', LoginView.as_view(), name='auth-login'),
    path('refresh', RefreshView.as_view(), name='auth-refresh'),
    path('logout', LogoutView.as_view(), name='auth-logout'),
    path('validate', ValidateView.as_view(), name='auth-validate'),
    path('users/lookup', UserLookupView.as_view(), name='auth-user-lookup'),
    path('users/by-ids', UsersByIdsView.as_view(), name='auth-users-by-ids'),
    path('change-password', ChangePasswordView.as_view(), name='auth-change-password'),
]

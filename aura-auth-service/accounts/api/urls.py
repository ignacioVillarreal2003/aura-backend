"""Auth API URL routes."""

from django.urls import path
from accounts.api.views import LoginView, RefreshView, IntrospectView, LogoutView, MeView

urlpatterns = [
    path('login', LoginView.as_view(), name='auth-login'),
    path('refresh', RefreshView.as_view(), name='auth-refresh'),
    path('introspect', IntrospectView.as_view(), name='auth-introspect'),
    path('logout', LogoutView.as_view(), name='auth-logout'),
    path('me', MeView.as_view(), name='auth-me'),
]

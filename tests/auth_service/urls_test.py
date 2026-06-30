from django.urls import path, include

urlpatterns = [
    path("auth/", include("apps.accounts.api.urls")),
]

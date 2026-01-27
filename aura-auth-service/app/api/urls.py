from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .controllers.controllers import UserViewSet, RoleViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'roles', RoleViewSet, basename='role')

app_name = 'api'

urlpatterns = [
    path('', include(router.urls)),
]

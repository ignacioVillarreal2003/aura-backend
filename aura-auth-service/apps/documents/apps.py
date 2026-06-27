"""AppConfig de la app documents."""
from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    """App de gestion de documentos."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.documents'
    verbose_name = 'Gestión de Documentos'

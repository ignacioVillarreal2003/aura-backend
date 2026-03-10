"""
AppConfig for documents application.
"""
from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    """
    Configuration for the documents application.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'documents'
    verbose_name = 'Gestión de Documentos'

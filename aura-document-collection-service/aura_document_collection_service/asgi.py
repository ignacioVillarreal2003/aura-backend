import os
from django.core.asgi import get_asgi_application

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "aura_document_collection_service.settings.production",
)

application = get_asgi_application()

from django.conf import settings
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = getattr(settings, "DEFAULT_PAGE_SIZE", 20)
    page_size_query_param = "page_size"
    max_page_size = getattr(settings, "MAX_PAGE_SIZE", 100)

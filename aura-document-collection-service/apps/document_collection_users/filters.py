import django_filters

from apps.document_collection_users.models import UserInDocumentCollection


class UserInDocumentCollectionFilter(django_filters.FilterSet):
    user_id = django_filters.NumberFilter()

    class Meta:
        model = UserInDocumentCollection
        fields: list[str] = []

import django_filters

from apps.document_collections.models import DocumentCollection


class DocumentCollectionFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    created_by = django_filters.NumberFilter()
    created_after = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = DocumentCollection
        fields: list[str] = []

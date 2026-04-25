import django_filters

from apps.document_collection_documents.models import DocumentInDocumentCollection


class DocumentInDocumentCollectionFilter(django_filters.FilterSet):
    document_id = django_filters.NumberFilter()
    document_name = django_filters.CharFilter(field_name="document__name", lookup_expr="icontains")

    class Meta:
        model = DocumentInDocumentCollection
        fields: list[str] = []

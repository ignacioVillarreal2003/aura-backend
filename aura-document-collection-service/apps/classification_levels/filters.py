import django_filters

from apps.classification_levels.models import ClassificationLevel


class ClassificationLevelFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    rank_gte = django_filters.NumberFilter(field_name="rank", lookup_expr="gte")
    rank_lte = django_filters.NumberFilter(field_name="rank", lookup_expr="lte")

    class Meta:
        model = ClassificationLevel
        fields: list[str] = []

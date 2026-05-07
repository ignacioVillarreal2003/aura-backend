import django_filters

from apps.compartments.models import Compartment


class CompartmentFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(field_name="name", lookup_expr="icontains")

    class Meta:
        model = Compartment
        fields: list[str] = []

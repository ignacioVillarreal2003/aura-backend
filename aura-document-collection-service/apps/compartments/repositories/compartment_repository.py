from django.db.models import QuerySet

from apps.compartments.models import Compartment


class CompartmentRepository:
    def list_all(self) -> QuerySet[Compartment]:
        return Compartment.objects.all()

    def get_by_id(self, compartment_id: int) -> Compartment | None:
        return Compartment.objects.filter(pk=compartment_id).first()

    def filter_by_ids(self, compartment_ids: list[int]) -> QuerySet[Compartment]:
        return Compartment.objects.filter(pk__in=compartment_ids)

    def create(self, name: str, description: str) -> Compartment:
        return Compartment.objects.create(name=name, description=description)

    def update(self, compartment: Compartment, name: str, description: str) -> Compartment:
        compartment.name = name
        compartment.description = description
        compartment.save(update_fields=["name", "description"])
        return compartment

    def delete(self, compartment: Compartment) -> None:
        compartment.delete()


compartment_repository = CompartmentRepository()

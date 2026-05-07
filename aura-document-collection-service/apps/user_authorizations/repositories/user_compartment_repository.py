from django.db.models import QuerySet

from apps.user_authorizations.models import UserCompartment


class UserCompartmentRepository:
    def list_by_user_id(self, user_id: int) -> QuerySet[UserCompartment]:
        return (
            UserCompartment.objects
            .select_related("compartment")
            .filter(user_id=user_id)
            .order_by("compartment__name")
        )

    def list_compartment_ids_by_user_id(self, user_id: int) -> list[int]:
        return list(
            UserCompartment.objects
            .filter(user_id=user_id)
            .values_list("compartment_id", flat=True)
        )

    def get_by_user_id_and_compartment_id(
        self,
        user_id: int,
        compartment_id: int,
    ) -> UserCompartment | None:
        return UserCompartment.objects.filter(
            user_id=user_id,
            compartment_id=compartment_id,
        ).first()

    def create(self, user_id: int, compartment_id: int, created_by: int) -> UserCompartment:
        return UserCompartment.objects.create(
            user_id=user_id,
            compartment_id=compartment_id,
            created_by=created_by,
        )

    def delete(self, user_compartment: UserCompartment) -> None:
        user_compartment.delete()


user_compartment_repository = UserCompartmentRepository()

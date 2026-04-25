from django.db.models import QuerySet

from apps.document_collection_users.models import UserInDocumentCollection


class UserInDocumentCollectionRepository:
    def list_active_by_document_collection_id(
        self, document_collection_id: int
    ) -> QuerySet[UserInDocumentCollection]:
        return (
            UserInDocumentCollection.objects.filter(document_collection_id=document_collection_id)
            .select_related("document_collection")
            .order_by()
        )

    def get_active_by_document_collection_id_and_user_id(
        self,
        document_collection_id: int,
        user_id: int,
    ) -> UserInDocumentCollection | None:
        return UserInDocumentCollection.objects.filter(
            document_collection_id=document_collection_id,
            user_id=user_id,
        ).first()

    def create(
        self,
        document_collection_id: int,
        user_id: int,
        created_by: int,
    ) -> UserInDocumentCollection:
        return UserInDocumentCollection.objects.create(
            document_collection_id=document_collection_id,
            user_id=user_id,
            created_by=created_by,
        )

    def soft_delete(self, user_in_document_collection: UserInDocumentCollection, deleted_by: int) -> None:
        user_in_document_collection.delete(deleted_by=deleted_by)


user_in_document_collection_repository = UserInDocumentCollectionRepository()

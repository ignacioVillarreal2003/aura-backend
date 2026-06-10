from django.db.models import Count, F, Q, QuerySet
from django.utils import timezone

from apps.document_collections.models import DocumentCollection


class DocumentCollectionRepository:
    def _base_qs(self) -> QuerySet[DocumentCollection]:
        return (
            DocumentCollection.objects
            .select_related("classification_level")
            .prefetch_related("compartments")
        )

    def get_active_by_id(self, document_collection_id: int) -> DocumentCollection | None:
        return self._base_qs().filter(pk=document_collection_id).first()

    def list_active(self) -> QuerySet[DocumentCollection]:
        return self._base_qs().order_by()

    def list_accessible(
        self,
        max_rank: int,
        compartment_ids: list[int],
    ) -> QuerySet[DocumentCollection]:
        qs = self._base_qs().filter(classification_level__rank__lte=max_rank)
        
        if not compartment_ids:
            return qs.annotate(total=Count("compartments", distinct=True)).filter(total=0)

        return (
            qs.annotate(
                total=Count("compartments", distinct=True),
                matched=Count(
                    "compartments",
                    filter=Q(compartments__id__in=compartment_ids),
                    distinct=True,
                ),
            )
            .filter(total=F("matched"))
        )

    def create(
        self,
        name: str,
        created_by: int,
        classification_level_id: int,
    ) -> DocumentCollection:
        return DocumentCollection.objects.create(
            name=name,
            created_by=created_by,
            classification_level_id=classification_level_id,
        )

    def update(
        self,
        document_collection: DocumentCollection,
        updated_by: int,
        name: str | None = None,
        classification_level_id: int | None = None,
    ) -> DocumentCollection:
        update_fields = ["updated_by", "updated_at"]
        document_collection.updated_by = updated_by
        document_collection.updated_at = timezone.now()
        if name is not None:
            document_collection.name = name
            update_fields.append("name")
        if classification_level_id is not None:
            document_collection.classification_level_id = classification_level_id
            update_fields.append("classification_level_id")
        document_collection.save(update_fields=update_fields)
        return document_collection

    def soft_delete(self, document_collection: DocumentCollection, deleted_by: int) -> None:
        document_collection.delete(deleted_by=deleted_by)


document_collection_repository = DocumentCollectionRepository()

from apps.document_collections.models import DocumentCollectionCompartment


class DocumentCollectionCompartmentRepository:
    def create(
        self,
        document_collection_id: int,
        compartment_id: int,
        created_by: int,
    ) -> DocumentCollectionCompartment:
        return DocumentCollectionCompartment.objects.create(
            document_collection_id=document_collection_id,
            compartment_id=compartment_id,
            created_by=created_by,
        )

    def delete_all_by_collection_id(self, document_collection_id: int) -> None:
        DocumentCollectionCompartment.objects.filter(
            document_collection_id=document_collection_id,
        ).delete()


document_collection_compartment_repository = DocumentCollectionCompartmentRepository()

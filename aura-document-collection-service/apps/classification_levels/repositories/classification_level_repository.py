from django.db.models import QuerySet

from apps.classification_levels.models import ClassificationLevel


class ClassificationLevelRepository:
    def list_all(self) -> QuerySet[ClassificationLevel]:
        return ClassificationLevel.objects.all()

    def get_by_id(self, classification_level_id: int) -> ClassificationLevel | None:
        return ClassificationLevel.objects.filter(pk=classification_level_id).first()

    def create(self, name: str, rank: int) -> ClassificationLevel:
        return ClassificationLevel.objects.create(name=name, rank=rank)

    def update(self, classification_level: ClassificationLevel, name: str, rank: int) -> ClassificationLevel:
        classification_level.name = name
        classification_level.rank = rank
        classification_level.save(update_fields=["name", "rank"])
        return classification_level

    def delete(self, classification_level: ClassificationLevel) -> None:
        classification_level.delete()


classification_level_repository = ClassificationLevelRepository()

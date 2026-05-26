from django.db import models


class ClassificationLevel(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    rank = models.PositiveSmallIntegerField(unique=True)
    description = models.TextField(blank=True, default='')

    class Meta:
        managed = False
        db_table = "classification_level"
        ordering = ["rank"]

    def __str__(self) -> str:
        return f"{self.name} (rank {self.rank})"

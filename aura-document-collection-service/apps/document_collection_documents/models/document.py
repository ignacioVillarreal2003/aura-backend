from django.db import models


class Document(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "document"

    def __str__(self) -> str:
        return self.name

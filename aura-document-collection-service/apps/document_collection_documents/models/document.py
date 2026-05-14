from django.db import models


class Document(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=255, default="application/octet-stream")
    storage_url = models.CharField(max_length=2048)
    file_size_bytes = models.BigIntegerField(default=0)
    created_by = models.BigIntegerField()
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "document"

    def __str__(self) -> str:
        return self.name

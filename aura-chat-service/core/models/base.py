from django.db import models
from django.utils import timezone


class AuditModel(models.Model):
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.BigIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk is not None:
            update_fields = kwargs.get("update_fields")
            if update_fields is None:
                self.updated_at = timezone.now()
            elif "updated_at" not in update_fields:
                self.updated_at = timezone.now()
                kwargs["update_fields"] = (*update_fields, "updated_at")
        super().save(*args, **kwargs)


class CreatedAuditModel(models.Model):
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

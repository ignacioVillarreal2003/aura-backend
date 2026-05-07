from django.db import models


class Compartment(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")

    class Meta:
        managed = False
        db_table = "compartment"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

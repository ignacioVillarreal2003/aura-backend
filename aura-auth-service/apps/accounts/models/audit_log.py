"""Modelo AuditLog (tabla audit_log de auth_db)."""

from django.db import models


class AuditLog(models.Model):
    """Registro de auditoria: solo se agregan filas, no se modifican ni borran."""

    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Fecha/Hora')
    actor_id = models.BigIntegerField(null=True, blank=True, verbose_name='ID actor')
    actor_username = models.CharField(
        max_length=255, null=True, blank=True, verbose_name='Usuario'
    )
    action = models.CharField(max_length=20, verbose_name='Acción')
    entity_type = models.CharField(max_length=100, verbose_name='Entidad')
    entity_id = models.CharField(max_length=255, null=True, blank=True, verbose_name='ID entidad')
    entity_label = models.CharField(
        max_length=255, null=True, blank=True, verbose_name='Nombre entidad'
    )
    details = models.JSONField(null=True, blank=True, verbose_name='Detalles')
    source = models.CharField(max_length=20, default='admin', verbose_name='Origen')

    class Meta:
        db_table = 'audit_log'
        managed = False
        verbose_name = 'Registro de auditoría'
        verbose_name_plural = 'Registros de auditoría'
        ordering = ['-timestamp']

    def __str__(self):
        return f'[{self.timestamp}] {self.actor_username} → {self.action} {self.entity_type}'

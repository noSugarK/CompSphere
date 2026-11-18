from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True
    )
    action = models.CharField(max_length=48)
    resource = models.CharField(max_length=32)
    resource_id = models.CharField(max_length=64)
    scope = models.JSONField(default=dict)
    detail = models.JSONField(default=dict)
    ip = models.GenericIPAddressField(null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "audit_logs"

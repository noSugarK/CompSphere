from django.conf import settings
from django.db import models
from django.utils import timezone


class BusinessModel(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class IdempotencyRecord(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    key = models.CharField(max_length=128)
    action = models.CharField(max_length=160)
    request_hash = models.CharField(max_length=64)
    result = models.JSONField(null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "api_idempotency_records"
        constraints = [
            models.UniqueConstraint(
                fields=["actor", "key", "action"],
                name="unique_idempotency_actor_action",
            )
        ]

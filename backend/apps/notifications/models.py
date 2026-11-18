from django.db import models
from django.utils import timezone


class AsyncOutbox(models.Model):
    topic = models.CharField(max_length=64)
    business_key = models.CharField(max_length=128, unique=True)
    payload = models.JSONField()
    status = models.CharField(max_length=16, default="pending")
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    lease_until = models.DateTimeField(null=True)
    dispatched_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "async_outbox"

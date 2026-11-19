from django.conf import settings
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


class RegistrationNotice(models.Model):
    class Kind(models.TextChoices):
        SUBMITTED = "submitted"
        APPROVED = "approved"
        REJECTED = "rejected"
        RETURNED = "returned"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    registration = models.ForeignKey(
        "registrations.Registration", on_delete=models.CASCADE
    )
    submission_no = models.PositiveIntegerField()
    kind = models.CharField(max_length=16, choices=Kind.choices)
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "registration_notices"
        indexes = [models.Index(fields=["recipient", "-created_at", "-id"])]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "registration", "submission_no", "kind"],
                name="uniq_registration_notice",
            )
        ]

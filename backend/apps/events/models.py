from django.db import models

from core.models import BusinessModel


class EventType(models.Model):
    code = models.CharField(max_length=16, primary_key=True)
    name = models.CharField(max_length=64)

    class Meta:
        db_table = "event_types"


class Event(BusinessModel):
    edition = models.ForeignKey("competitions.Edition", on_delete=models.PROTECT)
    code = models.ForeignKey(EventType, db_column="code", on_delete=models.PROTECT)
    name = models.CharField(max_length=64)
    min_members = models.PositiveIntegerField(default=1)
    max_members = models.PositiveIntegerField(default=3)
    coach_required = models.BooleanField(default=True)
    material_requirements = models.JSONField(default=list)
    status = models.CharField(max_length=16, default="enabled")

    class Meta:
        db_table = "competition_events"
        constraints = [
            models.UniqueConstraint(
                fields=["edition", "code"], name="unique_edition_event"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    min_members__gte=1, max_members__gte=models.F("min_members")
                ),
                name="event_members_valid",
            ),
        ]


class Offering(BusinessModel):
    edition = models.ForeignKey(
        "competitions.Edition", on_delete=models.PROTECT, related_name="offerings"
    )
    event = models.ForeignKey(Event, on_delete=models.PROTECT)
    group = models.ForeignKey("groups.Group", on_delete=models.PROTECT)
    quota = models.PositiveIntegerField(null=True)
    enroll_start = models.DateTimeField(null=True)
    enroll_end = models.DateTimeField(null=True)
    status = models.CharField(max_length=16, default="enabled")

    class Meta:
        db_table = "competition_offerings"
        constraints = [
            models.UniqueConstraint(
                fields=["edition", "event", "group"], name="unique_edition_offering"
            )
        ]

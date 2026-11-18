from django.db import models
from django.utils import timezone

from core.models import BusinessModel


class Season(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=64)
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=16, default="draft")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "seasons"
        constraints = [
            models.UniqueConstraint(
                fields=["is_default"],
                condition=models.Q(is_default=True),
                name="uniq_default_season",
            ),
            models.CheckConstraint(
                condition=models.Q(starts_on__lte=models.F("ends_on")),
                name="season_date_order",
            ),
            models.CheckConstraint(
                condition=models.Q(is_default=False) | models.Q(status="active"),
                name="default_season_active",
            ),
        ]


class Competition(BusinessModel):
    public_code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    summary = models.TextField(default="")
    category = models.CharField(max_length=32, null=True)
    level = models.CharField(max_length=16, null=True)
    status = models.CharField(max_length=16, default="draft")

    class Meta:
        db_table = "competitions"


class Edition(BusinessModel):
    competition = models.ForeignKey(
        Competition, on_delete=models.PROTECT, related_name="editions"
    )
    season = models.ForeignKey(Season, on_delete=models.PROTECT)
    edition_no = models.PositiveIntegerField(default=1)
    year = models.PositiveIntegerField()
    name = models.CharField(max_length=128)
    enroll_start = models.DateTimeField()
    enroll_end = models.DateTimeField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    venue = models.CharField(max_length=255, default="")
    status = models.CharField(max_length=16, default="draft")
    approval_mode = models.CharField(max_length=16, default="single")
    team_entry_mode = models.CharField(max_length=16, default="open")
    team_access_version = models.PositiveIntegerField(default=1)
    roster_publication = models.CharField(max_length=16, default="open")
    roster_publish_fields = models.JSONField(default=list)
    roster_published_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "competition_editions"
        constraints = [
            models.UniqueConstraint(
                fields=["competition", "year", "edition_no"],
                name="unique_competition_edition",
            ),
            models.CheckConstraint(
                condition=models.Q(enroll_start__lt=models.F("enroll_end")),
                name="edition_enroll_order",
            ),
            models.CheckConstraint(
                condition=models.Q(start_date__lte=models.F("end_date")),
                name="edition_event_order",
            ),
        ]

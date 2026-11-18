from django.db import models

from core.models import BusinessModel


class Group(BusinessModel):
    edition = models.ForeignKey("competitions.Edition", on_delete=models.PROTECT)
    code = models.CharField(max_length=8)
    name = models.CharField(max_length=64)
    school_level = models.CharField(max_length=8, null=True)
    enrollment_type = models.CharField(max_length=16, default="team")
    age_min = models.SmallIntegerField(null=True)
    age_max = models.SmallIntegerField(null=True)
    grade_limits = models.JSONField(default=list)
    status = models.CharField(max_length=16, default="enabled")

    class Meta:
        db_table = "competition_groups"
        constraints = [
            models.UniqueConstraint(
                fields=["edition", "code"], name="unique_edition_group"
            )
        ]

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from treebeard.mp_tree import MP_Node


class Organization(MP_Node):
    name: models.CharField[str, str] = models.CharField(max_length=128)
    code: models.CharField[str, str] = models.CharField(max_length=64, unique=True)
    org_type: models.CharField[str, str] = models.CharField(
        max_length=16, default="school"
    )
    status: models.CharField[str, str] = models.CharField(
        max_length=16, default="active"
    )
    created_at: models.DateTimeField = models.DateTimeField(default=timezone.now)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)
    is_deleted: models.BooleanField[bool, bool] = models.BooleanField(default=False)
    deleted_at: models.DateTimeField = models.DateTimeField(null=True)

    class Meta:
        db_table = "organizations"


class OrganizationMember(models.Model):
    org = models.ForeignKey(Organization, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    member_type = models.CharField(max_length=16, default="student")
    is_primary = models.BooleanField(default=True)
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organization_members"
        constraints = [
            models.UniqueConstraint(
                fields=["org", "user"],
                condition=models.Q(left_at__isnull=True),
                name="uniq_current_org_member",
            ),
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_primary=True, left_at__isnull=True),
                name="idx_org_member_primary",
            ),
        ]

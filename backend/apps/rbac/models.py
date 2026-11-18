from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class Permission(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=64)
    resource = models.CharField(max_length=32)
    action = models.CharField(max_length=32)

    class Meta:
        db_table = "permissions"


class Role(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=64)
    permissions: models.ManyToManyField[Permission, RolePermission] = (
        models.ManyToManyField(Permission, through="RolePermission")
    )

    class Meta:
        db_table = "roles"


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        db_table = "role_permissions"
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"], name="unique_role_permission"
            )
        ]


class UserRole(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="role_grants"
    )
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    scope_type = models.CharField(max_length=16)
    scope_id = models.PositiveBigIntegerField(null=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "user_roles"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "scope_type", "scope_id"],
                name="unique_user_role_scope",
                nulls_distinct=False,
            ),
            models.CheckConstraint(
                condition=models.Q(scope_type="global", scope_id__isnull=True)
                | models.Q(
                    scope_type__in=["org", "competition", "edition"],
                    scope_id__isnull=False,
                ),
                name="grant_scope_valid",
            ),
        ]

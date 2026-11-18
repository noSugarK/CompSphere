import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager["User"]):
    def create_user(self, email=None, password=None, **extra):
        user = self.model(
            email=self.normalize_email(email) if email else None,
            username=extra.pop("username", f"u_{uuid.uuid4().hex}"),
            **extra,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra):
        raise ValueError(
            "Use explicit RBAC role grants; no implicit Django superuser bypass."
        )


class User(AbstractBaseUser):
    username = models.CharField(max_length=64, unique=True)
    email = models.EmailField(max_length=255, unique=True, null=True, blank=True)
    email_verified_at = models.DateTimeField(null=True)
    password = models.CharField(max_length=255, db_column="password_hash")
    last_login = models.DateTimeField(null=True, db_column="last_login_at")
    phone = models.CharField(max_length=20, null=True)
    account_source = models.CharField(max_length=16, default="self")
    created_by = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, related_name="+"
    )
    created_by_org = models.ForeignKey(
        "orgs.Organization", on_delete=models.PROTECT, null=True, related_name="+"
    )
    must_change_password = models.BooleanField(default=False)
    initial_password_expires_at = models.DateTimeField(null=True)
    status = models.CharField(max_length=16, default="pending")
    token_version = models.PositiveIntegerField(default=0)
    affiliation_version = models.PositiveIntegerField(default=0)
    locale = models.CharField(max_length=10, default="zh-CN")
    theme = models.CharField(max_length=10, default="system")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True)
    objects = UserManager()
    USERNAME_FIELD = "username"

    @property
    def is_active(self):
        return self.status == "active" and not self.is_deleted

    @is_active.setter
    def is_active(self, value):
        self.status = "active" if value else "suspended"

    class Meta:
        db_table = "users"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(locale__in=["zh-CN", "en-US"]),
                name="user_locale_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(theme__in=["light", "dark", "system"]),
                name="user_theme_valid",
            ),
        ]

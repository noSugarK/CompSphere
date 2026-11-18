import os
from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.rbac.models import Role, UserRole


class Command(BaseCommand):
    help = "Initialize the first platform operator after seed_rbac; never reset an account."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        try:
            validate_email(email)
        except ValidationError:
            raise CommandError("A valid operator email is required.") from None
        try:
            role = Role.objects.select_for_update().get(code="platform_admin")
        except Role.DoesNotExist:
            raise CommandError(
                "Run seed_rbac before initializing the operator."
            ) from None
        if UserRole.objects.filter(role=role).exists():
            raise CommandError("Platform initialization is already complete.")
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError("Refusing to overwrite or promote an existing account.")
        # Read protected deployment-secret input or prompt; never expose it in argv/logs.
        password = os.environ.get("COMPSPHERE_BOOTSTRAP_PASSWORD")
        if password is None:
            password = getpass("Operator password: ")
            if password != getpass("Confirm password: "):
                raise CommandError("Passwords do not match.")
        try:
            validate_password(password, User(email=email))
        except ValidationError:
            raise CommandError(
                "The password does not meet the configured policy."
            ) from None
        user = User.objects.create_user(
            email=email,
            password=password,
            status="active",
            email_verified_at=timezone.now(),
        )
        UserRole.objects.create(
            user=user, role=role, scope_type="global", scope_id=None
        )
        self.stdout.write(self.style.SUCCESS("First platform operator initialized."))

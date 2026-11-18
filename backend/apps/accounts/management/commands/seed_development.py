import os

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.development import create_development_data


class Command(BaseCommand):
    help = "Create synthetic development fixtures, requiring an explicitly supplied strong password."

    def add_arguments(self, parser):
        parser.add_argument("--password", default=None)

    def handle(self, *args, **options):
        if not settings.IS_DEVELOPMENT:
            raise CommandError(
                "Development fixtures are disabled in production settings."
            )
        password = options["password"] or os.environ.get("COMPSPHERE_DEV_PASSWORD")
        if not password:
            raise CommandError(
                "Set COMPSPHERE_DEV_PASSWORD or pass --password; no default password exists."
            )
        validate_password(password)
        try:
            create_development_data(password)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                "Created synthetic fixtures. Accounts: platform, manager, coach, student, reviewer, organizer, outsider @dev.example. Password not displayed."
            )
        )

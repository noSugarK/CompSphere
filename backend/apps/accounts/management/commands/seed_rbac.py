from django.core.management.base import BaseCommand

from apps.rbac.seed import seed_rbac


class Command(BaseCommand):
    help = "Initialize permission and role definitions without accounts or credentials."

    def handle(self, *args, **options):
        seed_rbac()
        self.stdout.write(
            self.style.SUCCESS(
                "RBAC definitions initialized; no user accounts created."
            )
        )

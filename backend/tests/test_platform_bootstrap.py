from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User
from apps.rbac.models import Role, UserRole


@pytest.mark.django_db
def test_bootstrap_is_explicit_one_time_and_does_not_print_the_secret(monkeypatch):
    role = Role.objects.create(code="platform_admin", name="Platform operator")
    secret = "Synthetic-bootstrap-secret-48!"
    monkeypatch.setenv("COMPSPHERE_BOOTSTRAP_PASSWORD", secret)
    output = StringIO()
    call_command("bootstrap_platform", email="operator@example.invalid", stdout=output)
    user = User.objects.get(email="operator@example.invalid")
    assert user.check_password(secret)
    assert UserRole.objects.filter(user=user, role=role, scope_type="global").exists()
    assert secret not in output.getvalue()
    with pytest.raises(CommandError, match="already complete"):
        call_command("bootstrap_platform", email="second@example.invalid")
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_bootstrap_refuses_existing_account_and_weak_password(monkeypatch):
    Role.objects.create(code="platform_admin", name="Platform operator")
    user = User.objects.create_user(
        email="existing@example.invalid", password="original"
    )
    monkeypatch.setenv(
        "COMPSPHERE_BOOTSTRAP_PASSWORD", "Synthetic-bootstrap-secret-48!"
    )
    with pytest.raises(CommandError, match="existing account"):
        call_command("bootstrap_platform", email=user.email)
    user.refresh_from_db()
    assert user.check_password("original")
    assert not UserRole.objects.exists()
    monkeypatch.setenv("COMPSPHERE_BOOTSTRAP_PASSWORD", "123456789012")
    with pytest.raises(CommandError, match="password"):
        call_command("bootstrap_platform", email="new@example.invalid")
    assert not User.objects.filter(email="new@example.invalid").exists()

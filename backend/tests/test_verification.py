from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.db import OperationalError, connection, connections
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User, VerificationCode
from apps.accounts.services import issue_tokens
from apps.accounts.verification import (
    cleanup_expired_verifications,
    complete_delivery,
    prepare_verification_email,
    register_account,
    reset_password,
)
from apps.notifications.models import AsyncOutbox
from apps.rbac.models import UserRole
from apps.rbac.seed import seed_rbac
from core.crypto import decrypt
from core.exceptions import BusinessError

PASSWORD = "Synthetic-verification-2026!Strong"


def accept_code(email="new@example.test", purpose="register", **headers):
    response = APIClient().post(
        "/api/v1/auth/verify-code/send",
        {"email": email, "purpose": purpose},
        format="json",
        **headers,
    )
    assert response.status_code == 202, response.data
    item = VerificationCode.objects.latest("id")
    return item, decrypt(item.delivery_secret_enc)


def register(email, code, **extra):
    return APIClient().post(
        "/api/v1/auth/register",
        {
            "email": email,
            "password": PASSWORD,
            "verification_code": code,
            "real_name": "Synthetic participant",
            **extra,
        },
        format="json",
    )


@pytest.mark.django_db
def test_acceptance_does_not_query_accounts_and_does_not_reveal_secrets():
    with patch.object(
        User.objects,
        "filter",
        side_effect=AssertionError("Acceptance must not look up accounts"),
    ):
        item, code = accept_code("  NEW@EXAMPLE.TEST  ")
    assert item.target == "new@example.test"
    assert item.code_hash != code and code not in item.code_hash
    outbox = AsyncOutbox.objects.get(topic="auth.verification")
    assert outbox.payload == {"verification_code_id": item.id, "locale": "zh-CN"}
    assert item.target not in str(outbox.payload) and code not in str(outbox.payload)


@pytest.mark.django_db
def test_existing_and_unknown_email_have_identical_acceptance():
    User.objects.create_user(
        email="taken@example.test",
        password=PASSWORD,
        status="active",
        email_verified_at=timezone.now(),
    )
    responses = [
        APIClient().post(
            "/api/v1/auth/verify-code/send",
            {"email": email, "purpose": "register"},
            format="json",
        )
        for email in ("taken@example.test", "unknown@example.test")
    ]
    assert [r.status_code for r in responses] == [202, 202]
    assert all(r.data["data"] is None for r in responses)
    assert responses[0].data["message"] == responses[1].data["message"]
    assert VerificationCode.objects.count() == AsyncOutbox.objects.count() == 2


@pytest.mark.django_db
def test_registration_only_grants_participant_and_code_consumes_once():
    seed_rbac()
    item, code = accept_code()
    response = register(item.target, code)
    assert response.status_code == 201, response.data
    assert response.data["data"]["status"] == "active"
    assert not response.cookies and "access" not in response.data["data"]
    user = User.objects.get(pk=response.data["data"]["id"])
    assert user.email == item.target and user.email_verified_at is not None
    assert user.profile.person_type == "participant"
    assert list(
        UserRole.objects.filter(user=user).values_list(
            "role__code", "scope_type", "scope_id"
        )
    ) == [("participant", "global", None)]
    assert not UserRole.objects.filter(user=user, role__code="platform_admin").exists()
    item.refresh_from_db()
    assert item.consumed_at is not None and item.delivery_secret_enc is None
    assert register(item.target, code).status_code == 401
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_five_failed_attempts_are_persisted_before_error_response():
    seed_rbac()
    item, code = accept_code()
    wrong = "999999" if code != "999999" else "888888"
    for attempt in range(1, 6):
        response = register(item.target, wrong)
        assert response.status_code == 401 and response.data["code"] == 40102
        item.refresh_from_db()
        assert item.attempts == attempt
    assert register(item.target, code).status_code == 401
    item.refresh_from_db()
    assert item.consumed_at is not None and item.delivery_secret_enc is None


@pytest.mark.django_db
def test_expiry_resend_and_purpose_are_isolated():
    seed_rbac()
    item, code = accept_code()
    VerificationCode.objects.filter(pk=item.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert register(item.target, code).data["code"] == 40102
    cache.clear()
    new_item, new_code = accept_code()
    item.refresh_from_db()
    assert item.delivery_secret_enc is None and item.consumed_at is not None
    assert register(item.target, code).data["code"] == 40102
    wrong_purpose = APIClient().post(
        "/api/v1/auth/password/reset",
        {
            "email": new_item.target,
            "new_password": PASSWORD,
            "verification_code": new_code,
        },
        format="json",
    )
    assert wrong_purpose.status_code == 401 and wrong_purpose.data["code"] == 40102
    assert register(new_item.target, new_code).status_code == 201


@pytest.mark.django_db
def test_resend_invalidates_old_still_live_code():
    first, first_code = accept_code()
    cache.clear()
    second, second_code = accept_code()
    first.refresh_from_db()
    assert first.consumed_at is not None and first.delivery_secret_enc is None
    assert second.consumed_at is None
    assert first.code_hash != second.code_hash
    assert first_code not in str(AsyncOutbox.objects.values_list("payload", flat=True))
    assert isinstance(second_code, str)


@pytest.mark.django_db
def test_rate_limits_send_retry_after_and_purpose_has_own_email_interval():
    accept_code()
    client = APIClient()
    duplicate = client.post(
        "/api/v1/auth/verify-code/send",
        {"email": "new@example.test", "purpose": "register"},
        format="json",
    )
    assert duplicate.status_code == 429 and duplicate.data["code"] == 42901
    assert duplicate["Retry-After"] == "60"
    assert (
        client.post(
            "/api/v1/auth/verify-code/send",
            {"email": "new@example.test", "purpose": "reset_password"},
            format="json",
        ).status_code
        == 202
    )
    cache.clear()
    for index in range(20):
        assert (
            client.post(
                "/api/v1/auth/verify-code/send",
                {"email": f"person{index}@example.test", "purpose": "register"},
                format="json",
            ).status_code
            == 202
        )
    exhausted = client.post(
        "/api/v1/auth/verify-code/send",
        {"email": "last@example.test", "purpose": "register"},
        format="json",
    )
    assert exhausted.status_code == 429 and exhausted["Retry-After"] == "3600"


@pytest.mark.django_db
@override_settings(CODE_IP_HOURLY_LIMIT=1, TRUSTED_PROXY_IPS=["127.0.0.1/32"])
def test_trusted_proxy_clients_receive_independent_ip_budgets():
    client = APIClient()
    first = client.post(
        "/api/v1/auth/verify-code/send",
        {"email": "first@example.test", "purpose": "register"},
        format="json",
        REMOTE_ADDR="127.0.0.1",
        HTTP_X_REAL_IP="198.51.100.1",
    )
    second = client.post(
        "/api/v1/auth/verify-code/send",
        {"email": "second@example.test", "purpose": "register"},
        format="json",
        REMOTE_ADDR="127.0.0.1",
        HTTP_X_REAL_IP="198.51.100.2",
    )
    exhausted = client.post(
        "/api/v1/auth/verify-code/send",
        {"email": "third@example.test", "purpose": "register"},
        format="json",
        REMOTE_ADDR="127.0.0.1",
        HTTP_X_REAL_IP="198.51.100.1",
    )
    assert first.status_code == second.status_code == 202
    assert exhausted.status_code == 429
    assert set(VerificationCode.objects.values_list("client_ip", flat=True)) == {
        "198.51.100.1",
        "198.51.100.2",
    }


@pytest.mark.django_db
@override_settings(CODE_IP_HOURLY_LIMIT=1, TRUSTED_PROXY_IPS=[])
def test_untrusted_sender_cannot_rotate_spoofed_proxy_headers():
    client = APIClient()
    first = client.post(
        "/api/v1/auth/verify-code/send",
        {"email": "first@example.test", "purpose": "register"},
        format="json",
        REMOTE_ADDR="203.0.113.2",
        HTTP_X_REAL_IP="198.51.100.1",
    )
    spoofed = client.post(
        "/api/v1/auth/verify-code/send",
        {"email": "second@example.test", "purpose": "register"},
        format="json",
        REMOTE_ADDR="203.0.113.2",
        HTTP_X_REAL_IP="198.51.100.2",
    )
    assert first.status_code == 202 and spoofed.status_code == 429
    assert VerificationCode.objects.get().client_ip == "203.0.113.2"


@pytest.mark.django_db
def test_acceptance_storage_failure_rolls_back_code_and_outbox():
    with patch(
        "apps.notifications.services.queue_verification",
        side_effect=OperationalError("Synthetic storage failure"),
    ):
        response = APIClient().post(
            "/api/v1/auth/verify-code/send",
            {"email": "new@example.test", "purpose": "register"},
            format="json",
        )
    assert response.status_code == 503 and response.data["code"] == 50301
    assert VerificationCode.objects.count() == AsyncOutbox.objects.count() == 0
    assert "Synthetic storage failure" not in str(response.data)


@pytest.mark.django_db
def test_cache_failure_is_closed_and_no_code_is_accepted():
    with patch(
        "apps.accounts.verification.cache.add",
        side_effect=ConnectionError("Synthetic cache failure"),
    ):
        response = APIClient().post(
            "/api/v1/auth/verify-code/send",
            {"email": "new@example.test", "purpose": "register"},
            format="json",
        )
    assert response.status_code == 503 and response.data["code"] == 50301
    assert VerificationCode.objects.count() == 0


@pytest.mark.django_db
def test_reset_password_invalidates_sessions_without_changing_grants():
    seed_rbac()
    user = User.objects.create_user(
        email="student@example.test",
        password=PASSWORD,
        status="active",
        email_verified_at=timezone.now(),
        must_change_password=True,
    )
    old_access, _ = issue_tokens(user)
    item, code = accept_code(user.email, "reset_password")
    response = APIClient().post(
        "/api/v1/auth/password/reset",
        {
            "email": user.email,
            "new_password": "Replacement-flow-2026!Strong",
            "verification_code": code,
        },
        format="json",
    )
    assert response.status_code == 202 and response.data["data"] is None
    user.refresh_from_db()
    assert user.check_password("Replacement-flow-2026!Strong")
    assert user.token_version == 1 and not user.must_change_password
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer " + old_access["access"])
    assert client.get("/api/v1/me").status_code == 401
    assert (
        APIClient()
        .post(
            "/api/v1/auth/password/reset",
            {"email": user.email, "new_password": PASSWORD, "verification_code": code},
            format="json",
        )
        .data["code"]
        == 40102
    )


@pytest.mark.django_db
@pytest.mark.parametrize("state,deleted", [("suspended", False), ("active", True)])
def test_password_reset_never_reactivates_blocked_or_deleted_account(state, deleted):
    user = User.objects.create_user(
        email="blocked@example.test",
        password=PASSWORD,
        status=state,
        is_deleted=deleted,
        email_verified_at=timezone.now(),
    )
    _, code = accept_code(user.email, "reset_password")
    response = APIClient().post(
        "/api/v1/auth/password/reset",
        {
            "email": user.email,
            "new_password": "Replacement-flow-2026!Strong",
            "verification_code": code,
        },
        format="json",
    )
    assert response.status_code == 202
    user.refresh_from_db()
    assert user.status == state and user.is_deleted == deleted
    assert user.check_password(PASSWORD) and user.token_version == 0


@pytest.mark.django_db
def test_async_eligibility_and_delivery_cleanup():
    User.objects.create_user(
        email="taken@example.test",
        password=PASSWORD,
        status="active",
        email_verified_at=timezone.now(),
    )
    taken, _ = accept_code("taken@example.test")
    assert prepare_verification_email(taken.id, "zh-CN") is None
    taken.refresh_from_db()
    assert taken.delivery_secret_enc is None
    missing, _ = accept_code("unknown@example.test", "reset_password")
    assert prepare_verification_email(missing.id, "en-US") is None
    item, code = accept_code()
    english = prepare_verification_email(item.id, "en-US")
    chinese = prepare_verification_email(item.id, "zh-CN")
    assert code in english.body and code in chinese.body
    assert english.to == [item.target]
    assert english.extra_headers["Message-ID"] == chinese.extra_headers["Message-ID"]
    complete_delivery(item.id)
    item.refresh_from_db()
    assert item.delivery_secret_enc is None
    cache.clear()
    expired, _ = accept_code("expired@example.test")
    VerificationCode.objects.filter(pk=expired.id).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert cleanup_expired_verifications() >= 1
    expired.refresh_from_db()
    assert expired.delivery_secret_enc is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "update",
    [
        {"verification_code": 123456},
        {"verification_code": "１２３４５６"},
        {"verification_code": "12345"},
        {"real_name": "   "},
        {"real_name": 123},
        {"role": "platform_admin"},
        {"password": True},
    ],
)
def test_register_strict_boundary_rejects_invalid_types_and_injected_roles(update):
    response = register("new@example.test", "000001", **update)
    assert response.status_code == 400 and response.data["code"] == 40001


@pytest.mark.django_db
def test_password_policy_does_not_consume_valid_code_and_email_manager_normalizes():
    seed_rbac()
    item, code = accept_code()
    response = register(item.target, code, password="111111111111")
    assert response.status_code == 400
    item.refresh_from_db()
    assert item.consumed_at is None and item.attempts == 0
    assert register(item.target, code).status_code == 201
    user = User.objects.create_user(email=" Upper@Example.Test ", password=PASSWORD)
    assert user.email == "upper@example.test"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("purpose", ["register", "reset_password"])
def test_postgresql_verification_is_consumed_only_once(purpose):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-locking verification")
    seed_rbac()
    if purpose == "reset_password":
        User.objects.create_user(
            email="concurrent@example.test",
            password=PASSWORD,
            status="active",
            email_verified_at=timezone.now(),
        )
    item, code = accept_code("concurrent@example.test", purpose)
    barrier = Barrier(2)

    def consume(index):
        try:
            barrier.wait(timeout=10)
            try:
                if purpose == "register":
                    register_account(
                        item.target, PASSWORD, code, "Concurrent synthetic participant"
                    )
                else:
                    reset_password(
                        item.target, code, "Replacement-recovery-2026!Strong"
                    )
                return "success"
            except BusinessError as exc:
                return str(exc.code)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(consume, [1, 2]))
    assert sorted(results) == ["40102", "success"]
    assert User.objects.filter(email=item.target).count() == 1
    item.refresh_from_db()
    assert item.consumed_at is not None and item.delivery_secret_enc is None
    if purpose == "reset_password":
        assert User.objects.get(email=item.target).token_version == 1

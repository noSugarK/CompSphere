from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core import mail
from django.core.mail import EmailMessage
from django.utils import timezone

from apps.notifications.models import AsyncOutbox
from apps.notifications.services import queue_verification
from apps.notifications.tasks import (
    claim_delivery,
    deliver_claim,
    dispatch_registration_mail,
)

pytestmark = pytest.mark.django_db


def test_supported_delivery_and_secret_free_payload():
    row = queue_verification(17, "zh-CN")
    legacy = AsyncOutbox.objects.create(
        topic="registration.submitted",
        business_key="registration.submitted:1:1",
        payload={"resource_id": 1, "version": 1, "actor_id": 1},
    )
    assert row.payload == {"verification_code_id": 17, "locale": "zh-CN"}
    with (
        patch("apps.notifications.tasks.prepare_verification_email") as prepare,
        patch("apps.notifications.tasks.complete_delivery") as complete,
    ):
        prepare.return_value = EmailMessage(
            "Synthetic", "000001", to=["a@example.test"]
        )
        claimed = claim_delivery()
        assert claimed.pk == row.pk
        assert claim_delivery() is None
        deliver_claim(claimed)
        complete.assert_called_once_with(17)
    row.refresh_from_db()
    assert row.status == "dispatched"
    assert mail.outbox[-1].extra_headers["Message-ID"] == (
        f"<verification-{row.pk}@compsphere.invalid>"
    )
    dispatch_registration_mail()
    legacy.refresh_from_db()
    assert legacy.status == "pending" and legacy.attempts == 0


def test_failed_send_retries_without_leaking_exception(capsys):
    row = queue_verification(18, "en-US")
    with (
        patch("apps.notifications.tasks.prepare_verification_email") as prepare,
        patch("apps.notifications.tasks.complete_delivery") as complete,
    ):
        prepare.side_effect = RuntimeError("SECRET recipient code body")
        deliver_claim(claim_delivery())
        complete.assert_not_called()
    row.refresh_from_db()
    assert row.status == "pending" and row.attempts == 1
    assert row.lease_until is None and row.next_attempt_at > timezone.now()
    assert "SECRET" not in capsys.readouterr().out
    assert claim_delivery() is None


def test_expired_lease_reclaimed_and_stale_worker_cannot_finalize():
    row = queue_verification(19, "en-US")
    first = claim_delivery()
    AsyncOutbox.objects.filter(pk=row.pk).update(
        lease_until=timezone.now() - timedelta(seconds=1)
    )
    second = claim_delivery()
    assert second.attempts == 2
    with (
        patch("apps.notifications.tasks.prepare_verification_email", return_value=None),
        patch("apps.notifications.tasks.complete_delivery"),
    ):
        deliver_claim(first)
        row.refresh_from_db()
        assert row.status == "pending" and row.lease_until == second.lease_until
        deliver_claim(second)
    row.refresh_from_db()
    assert row.status == "dispatched"


def test_exhausted_and_invalid_records_do_not_send(settings, capsys):
    settings.OUTBOX_MAX_ATTEMPTS = 1
    row = queue_verification(20, "en-US")
    row.payload["email"] = "private@example.test"
    row.save()
    with patch("apps.notifications.tasks.prepare_verification_email") as prepare:
        deliver_claim(claim_delivery())
        prepare.assert_not_called()
    row.refresh_from_db()
    assert row.status == "failed"
    exhausted = queue_verification(21, "en-US")
    exhausted.attempts = 1
    exhausted.lease_until = timezone.now() - timedelta(seconds=1)
    exhausted.save()
    assert claim_delivery() is None
    exhausted.refresh_from_db()
    assert exhausted.status == "failed"
    logs = capsys.readouterr().out
    assert "outbox.failed" in logs and "LeaseExpired" in logs
    assert "private@example.test" not in logs


def test_exhausted_backlog_cannot_exceed_retry_limit(settings):
    settings.OUTBOX_BATCH_SIZE = 2
    for code_id in range(30, 33):
        row = queue_verification(code_id, "en-US")
        row.attempts = settings.OUTBOX_MAX_ATTEMPTS
        row.save(update_fields=["attempts"])
    assert claim_delivery() is None
    assert claim_delivery() is None
    assert AsyncOutbox.objects.filter(status="failed").count() == 3
    assert not AsyncOutbox.objects.filter(
        attempts__gt=settings.OUTBOX_MAX_ATTEMPTS
    ).exists()

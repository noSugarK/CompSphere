"""Durable, leased delivery. SMTP acceptance can precede a worker crash/retry."""

import time
from datetime import timedelta

import structlog
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.verification import (
    cleanup_expired_verifications,
    complete_delivery,
    prepare_verification_email,
)
from apps.notifications.models import AsyncOutbox

logger = structlog.get_logger()
TOPIC = "auth.verification"


def claim_delivery():
    now = timezone.now()
    available = Q(lease_until__isnull=True) | Q(lease_until__lte=now)
    with transaction.atomic():
        rows = AsyncOutbox.objects.filter(topic=TOPIC, status="pending").filter(
            available
        )
        exhausted = list(
            rows.filter(attempts__gte=settings.OUTBOX_MAX_ATTEMPTS)
            .select_for_update(skip_locked=True)
            .order_by("pk")[: settings.OUTBOX_BATCH_SIZE]
        )
        for failed in exhausted:
            failed.status = "failed"
            failed.lease_until = None
            failed.save(update_fields=["status", "lease_until"])
            logger.warning(
                "outbox.failed",
                outbox_id=failed.pk,
                attempts=failed.attempts,
                error_type="LeaseExpired",
            )
        row = (
            rows.filter(
                next_attempt_at__lte=now, attempts__lt=settings.OUTBOX_MAX_ATTEMPTS
            )
            .select_for_update(skip_locked=True)
            .order_by("next_attempt_at", "pk")
            .first()
        )
        if row is None:
            return None
        row.attempts += 1
        row.lease_until = now + timedelta(seconds=settings.OUTBOX_LEASE_SECONDS)
        row.save(update_fields=["attempts", "lease_until"])
        logger.info("outbox.claimed", outbox_id=row.pk, retry_no=row.attempts - 1)
        return row


def deliver_claim(row):
    started = time.monotonic()
    failure = None
    try:
        payload = row.payload
        if (
            not isinstance(payload, dict)
            or set(payload) != {"verification_code_id", "locale"}
            or type(payload["verification_code_id"]) is not int
            or not 1 <= payload["verification_code_id"] <= 9_007_199_254_740_991
            or payload["locale"] not in ("zh-CN", "en-US")
        ):
            raise ValueError("Invalid verification delivery payload")
        message = prepare_verification_email(
            payload["verification_code_id"], payload["locale"]
        )
        if message is not None:
            # Stable across retries; recipients/mail servers may deduplicate it.
            message.extra_headers["Message-ID"] = (
                f"<verification-{row.pk}@compsphere.invalid>"
            )
            if message.send(fail_silently=False) != 1:
                raise RuntimeError("Mail backend did not accept message")
        complete_delivery(payload["verification_code_id"])
    except Exception as exc:
        # SMTP exceptions may contain recipient addresses; never log their text.
        failure = type(exc).__name__

    now = timezone.now()
    current = AsyncOutbox.objects.filter(
        pk=row.pk, status="pending", attempts=row.attempts, lease_until=row.lease_until
    )
    if failure is None:
        changed = current.update(
            status="dispatched", dispatched_at=now, lease_until=None
        )
        state = "dispatched"
    else:
        state = "failed" if row.attempts >= settings.OUTBOX_MAX_ATTEMPTS else "pending"
        changed = current.update(
            status=state,
            lease_until=None,
            next_attempt_at=now
            + timedelta(seconds=min(30 * 2 ** (row.attempts - 1), 3600)),
        )
    log = logger.warning if failure is not None else logger.info
    log(
        "outbox.delivery",
        outbox_id=row.pk,
        retry_no=row.attempts - 1,
        result_state=state if changed else "stale_claim",
        error_type=failure,
        duration_ms=round((time.monotonic() - started) * 1000, 2),
    )


@shared_task(ignore_result=True)
def dispatch_verification_mail():
    cleanup_expired_verifications()
    for _ in range(settings.OUTBOX_BATCH_SIZE):
        row = claim_delivery()
        if row is None:
            break
        deliver_claim(row)

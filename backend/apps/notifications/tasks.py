"""Durable, leased delivery. SMTP acceptance can precede a worker crash/retry."""

import time
from datetime import timedelta

import structlog
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.verification import (
    cleanup_expired_verifications,
    complete_delivery,
    prepare_verification_email,
)
from apps.notifications.models import AsyncOutbox
from apps.notifications.services import (
    REGISTRATION_MAIL_TOPIC,
    VERIFICATION_MAIL_TOPIC,
    visible_notices,
)

logger = structlog.get_logger()
REGISTRATION_MAIL_SUBJECTS = {
    "zh-CN": {
        "submitted": "竞云｜报名已提交",
        "approved": "竞云｜报名审核通过",
        "rejected": "竞云｜报名被驳回",
        "returned": "竞云｜报名已退回修改",
    },
    "en-US": {
        "submitted": "CompSphere | Registration submitted",
        "approved": "CompSphere | Registration approved",
        "rejected": "CompSphere | Registration rejected",
        "returned": "CompSphere | Registration returned for changes",
    },
}
REGISTRATION_MAIL_BODIES = {
    "zh-CN": "你的报名有新进展。请登录竞云消息中心查看详情：\n{url}",
    "en-US": "There is an update to your registration. Sign in to CompSphere to view it:\n{url}",
}


def claim_delivery(topic=VERIFICATION_MAIL_TOPIC):
    now = timezone.now()
    available = Q(lease_until__isnull=True) | Q(lease_until__lte=now)
    with transaction.atomic():
        rows = AsyncOutbox.objects.filter(topic=topic, status="pending").filter(
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


def delivery_payload(payload, id_field):
    if (
        not isinstance(payload, dict)
        or set(payload) != {id_field, "locale"}
        or type(payload[id_field]) is not int
        or not 1 <= payload[id_field] <= 9_007_199_254_740_991
        or payload["locale"] not in ("zh-CN", "en-US")
    ):
        raise ValueError("Invalid mail delivery payload")
    return payload[id_field], payload["locale"]


def prepare_registration_email(notice_id, locale, queued_at):
    notice = (
        visible_notices()
        .filter(pk=notice_id, recipient__email_verified_at__lte=queued_at)
        .select_related("recipient")
        .first()
    )
    if notice is None or not notice.recipient.is_active or not notice.recipient.email:
        return None
    return EmailMessage(
        subject=REGISTRATION_MAIL_SUBJECTS[locale][notice.kind],
        body=REGISTRATION_MAIL_BODIES[locale].format(
            url=f"{settings.SITE_BASE_URL.rstrip('/')}/notifications"
        ),
        to=[notice.recipient.email],
    )


def send_message(message, message_id):
    if message is not None:
        message.extra_headers["Message-ID"] = f"<{message_id}@compsphere.invalid>"
        if message.send(fail_silently=False) != 1:
            raise RuntimeError("Mail backend did not accept message")


def deliver_claim(row):
    started = time.monotonic()
    failure = None
    message = None
    try:
        if row.topic == VERIFICATION_MAIL_TOPIC:
            code_id, locale = delivery_payload(row.payload, "verification_code_id")
            message = prepare_verification_email(code_id, locale)
            send_message(message, f"verification-{row.pk}")
            complete_delivery(code_id)
        elif row.topic == REGISTRATION_MAIL_TOPIC:
            notice_id, locale = delivery_payload(row.payload, "notice_id")
            message = prepare_registration_email(notice_id, locale, row.created_at)
            send_message(message, f"registration-{row.pk}")
        else:
            raise ValueError("Unsupported mail topic")
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
        state = "dispatched" if message is not None else "skipped"
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
        topic=row.topic,
        retry_no=row.attempts - 1,
        result_state=state if changed else "stale_claim",
        error_type=failure,
        duration_ms=round((time.monotonic() - started) * 1000, 2),
    )


def dispatch_mail(topic):
    for _ in range(settings.OUTBOX_BATCH_SIZE):
        row = claim_delivery(topic)
        if row is None:
            break
        deliver_claim(row)


@shared_task(ignore_result=True)
def dispatch_verification_mail():
    cleanup_expired_verifications()
    dispatch_mail(VERIFICATION_MAIL_TOPIC)


@shared_task(ignore_result=True)
def dispatch_registration_mail():
    dispatch_mail(REGISTRATION_MAIL_TOPIC)

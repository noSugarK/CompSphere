from django.utils import timezone

from apps.notifications.models import AsyncOutbox, RegistrationNotice

VERIFICATION_MAIL_TOPIC = "auth.verification"
REGISTRATION_MAIL_TOPIC = "registration.notice_mail"


def queue_verification(verification_code_id, locale):
    return AsyncOutbox.objects.create(
        topic=VERIFICATION_MAIL_TOPIC,
        business_key=f"{VERIFICATION_MAIL_TOPIC}:{verification_code_id}",
        payload={"verification_code_id": verification_code_id, "locale": locale},
    )


def record_registration_notice(registration, submission_no, kind):
    """Record an inbox item and its mail job inside the registration transaction."""
    notice, created = RegistrationNotice.objects.get_or_create(
        recipient_id=registration.submitted_by_id,
        registration=registration,
        submission_no=submission_no,
        kind=kind,
    )
    if not created:
        return
    recipient = registration.submitted_by
    if recipient.is_active and recipient.email and recipient.email_verified_at:
        AsyncOutbox.objects.create(
            topic=REGISTRATION_MAIL_TOPIC,
            business_key=f"{REGISTRATION_MAIL_TOPIC}:{notice.pk}",
            payload={"notice_id": notice.pk, "locale": recipient.locale},
        )


def visible_notices():
    return RegistrationNotice.objects.filter(registration__is_deleted=False).exclude(
        registration__edition__status="closed"
    )


def inbox(user):
    return visible_notices().filter(recipient=user).order_by("-created_at", "-id")


def mark_read(user, notice_id):
    notices = inbox(user).filter(pk=notice_id)
    notices.filter(read_at__isnull=True).update(read_at=timezone.now())
    return notices.get()

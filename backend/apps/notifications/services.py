from django.utils import timezone

from apps.notifications.models import AsyncOutbox, RegistrationNotice


def queue_verification(verification_code_id, locale):
    return AsyncOutbox.objects.create(
        topic="auth.verification",
        business_key=f"auth.verification:{verification_code_id}",
        payload={"verification_code_id": verification_code_id, "locale": locale},
    )


def queue_event(topic, resource_id, version, actor_id):
    AsyncOutbox.objects.get_or_create(
        business_key=f"{topic}:{resource_id}:{version}",
        defaults={
            "topic": topic,
            "payload": {
                "resource_id": resource_id,
                "version": version,
                "actor_id": actor_id,
            },
        },
    )


def record_registration_notice(registration, submission_no, kind):
    RegistrationNotice.objects.get_or_create(
        recipient_id=registration.submitted_by_id,
        registration=registration,
        submission_no=submission_no,
        kind=kind,
    )


def inbox(user):
    return (
        RegistrationNotice.objects.filter(
            recipient=user, registration__is_deleted=False
        )
        .exclude(registration__edition__status="closed")
        .order_by("-created_at", "-id")
    )


def mark_read(user, notice_id):
    notices = inbox(user).filter(pk=notice_id)
    notices.filter(read_at__isnull=True).update(read_at=timezone.now())
    return notices.get()

from apps.notifications.models import AsyncOutbox


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

from apps.notifications.models import AsyncOutbox


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

from django.db import transaction

from apps.audit.services import audit
from apps.competitions.services import configuration_edition
from apps.events.models import Event, EventType


@transaction.atomic
def create_event(actor, edition_id, data):
    edition = configuration_edition(actor, edition_id, "event:create", draft_write=True)
    event_type = EventType.objects.get(pk=data["event_code"])
    item = Event.objects.create(
        edition=edition,
        code=event_type,
        name=data["name"],
        min_members=data["min_members"],
        max_members=data["max_members"],
        coach_required=data["coach_required"],
    )
    audit(actor, "event.created", "event", item.id, scope={"edition_id": edition.id})
    return item

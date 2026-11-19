from django.db import transaction
from django.utils import timezone

from apps.audit.services import audit
from apps.competitions.services import configuration_edition
from apps.events.models import Event, EventType, Offering
from apps.groups.models import Group
from core.constants import CONFIGURATION_TRANSITIONS
from core.exceptions import BusinessError
from core.state import transition


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


@transaction.atomic
def create_offering(actor, edition_id, data):
    edition = configuration_edition(
        actor, edition_id, "edition:update", draft_write=True
    )
    event = Event.objects.get(pk=data["event_id"], edition=edition, is_deleted=False)
    group = Group.objects.get(pk=data["group_id"], edition=edition, is_deleted=False)
    if event.status != "enabled" or group.status != "enabled":
        raise BusinessError(
            40902, "Enable the event and division before opening this combination"
        )
    item, created = Offering.objects.get_or_create(
        edition=edition, event=event, group=group
    )
    if not created:
        if not item.is_deleted:
            raise BusinessError(40901, "This registration combination already exists")
        item.is_deleted = False
        item.deleted_at = None
        item.status = "enabled"
        item.save(update_fields=["is_deleted", "deleted_at", "status", "updated_at"])
    audit(
        actor, "offering.created", "offering", item.pk, scope={"edition_id": edition.id}
    )
    return item


def locked_offering(actor, offering_id, *, draft_write=False):
    edition_id = Offering.objects.values_list("edition_id", flat=True).get(
        pk=offering_id, is_deleted=False
    )
    edition = configuration_edition(
        actor, edition_id, "edition:update", draft_write=draft_write, lock=True
    )
    item = Offering.objects.select_related("event", "group").get(
        pk=offering_id, is_deleted=False
    )
    if edition.status == "closed":
        raise BusinessError(40902, "Closed editions are read-only")
    return item


@transaction.atomic
def change_offering_state(actor, offering_id, action):
    item = locked_offering(actor, offering_id)
    if action == "enable" and (
        item.event.status != "enabled" or item.group.status != "enabled"
    ):
        raise BusinessError(40902, "Enable the event and division first")
    transition(item, action, CONFIGURATION_TRANSITIONS)
    item.save(update_fields=["status", "updated_at"])
    audit(
        actor,
        f"offering.{item.status}",
        "offering",
        item.pk,
        scope={"edition_id": item.edition_id},
    )
    return item


@transaction.atomic
def delete_offering(actor, offering_id):
    item = locked_offering(actor, offering_id, draft_write=True)
    if item.registration_set.exists():
        raise BusinessError(
            40902, "An offering with registration records cannot be deleted"
        )
    item.is_deleted = True
    item.deleted_at = timezone.now()
    item.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
    audit(
        actor,
        "offering.deleted",
        "offering",
        item.pk,
        scope={"edition_id": item.edition_id},
    )

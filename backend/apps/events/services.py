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


def locked_event(actor, event_id, permission, *, draft_write=False):
    edition_id = Event.objects.values_list("edition_id", flat=True).get(
        pk=event_id, is_deleted=False
    )
    edition = configuration_edition(
        actor, edition_id, permission, draft_write=draft_write, lock=True
    )
    if edition.status == "closed":
        raise BusinessError(40902, "Closed editions are read-only")
    return Event.objects.get(pk=event_id, is_deleted=False)


@transaction.atomic
def update_event(actor, event_id, data):
    item = locked_event(actor, event_id, "event:update", draft_write=True)
    if not data:
        return item
    if data.get("min_members", item.min_members) > data.get(
        "max_members", item.max_members
    ):
        raise BusinessError(
            40001, "Maximum participants cannot be below the minimum", 400
        )
    for field, value in data.items():
        setattr(item, field, value)
    item.save(update_fields=[*data, "updated_at"])
    audit(
        actor, "event.updated", "event", item.pk, scope={"edition_id": item.edition_id}
    )
    return item


@transaction.atomic
def delete_event(actor, event_id):
    item = locked_event(actor, event_id, "event:update", draft_write=True)
    if item.offering_set.filter(is_deleted=False).exists():
        raise BusinessError(
            40902, "Detach the event from all offerings before deleting it"
        )
    item.is_deleted = True
    item.deleted_at = timezone.now()
    item.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
    audit(
        actor, "event.deleted", "event", item.pk, scope={"edition_id": item.edition_id}
    )


@transaction.atomic
def change_event_state(actor, event_id, action):
    item = locked_event(actor, event_id, "event:enable_disable")
    transition(item, action, CONFIGURATION_TRANSITIONS)
    item.save(update_fields=["status", "updated_at"])
    audit(
        actor,
        f"event.{item.status}",
        "event",
        item.pk,
        scope={"edition_id": item.edition_id},
    )
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
        item.enroll_start = item.enroll_end = item.quota = None
        item.save(
            update_fields=[
                "is_deleted",
                "deleted_at",
                "status",
                "enroll_start",
                "enroll_end",
                "quota",
                "updated_at",
            ]
        )
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
    item = Offering.objects.select_related("event", "group", "edition").get(
        pk=offering_id, is_deleted=False
    )
    if edition.status == "closed":
        raise BusinessError(40902, "Closed editions are read-only")
    return item


@transaction.atomic
def update_offering(actor, offering_id, data):
    item = locked_offering(actor, offering_id, draft_write=True)
    if not data:
        return item
    for field, value in data.items():
        setattr(item, field, value)
    start, end = item.registration_window(item.edition)
    if not start < end <= item.edition.start_date:
        raise BusinessError(
            42203,
            "Registration must open before it closes and close before the event starts",
            422,
        )
    item.save(update_fields=[*data, "updated_at"])
    audit(
        actor,
        "offering.updated",
        "offering",
        item.pk,
        scope={"edition_id": item.edition_id},
    )
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

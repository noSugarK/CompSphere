from django.db import transaction
from django.utils import timezone

from apps.audit.services import audit
from apps.competitions.services import configuration_edition
from apps.groups.models import Group
from core.constants import CONFIGURATION_TRANSITIONS
from core.exceptions import BusinessError
from core.state import transition


@transaction.atomic
def create_group(actor, edition_id, data):
    edition = configuration_edition(actor, edition_id, "group:create", draft_write=True)
    group = Group.objects.create(edition=edition, **data)
    audit(actor, "group.created", "group", group.pk, scope={"edition_id": edition.id})
    return group


@transaction.atomic
def update_group(actor, group_id, data):
    group = Group.objects.get(pk=group_id, is_deleted=False)
    configuration_edition(actor, group.edition_id, "group:update", draft_write=True)
    group.refresh_from_db()
    if group.is_deleted:
        raise BusinessError(40401, "Division not found", 404)
    if not data:
        return group
    for field, value in data.items():
        setattr(group, field, value)
    group.save(update_fields=[*data, "updated_at"])
    audit(
        actor,
        "group.updated",
        "group",
        group.pk,
        scope={"edition_id": group.edition_id},
    )
    return group


@transaction.atomic
def delete_group(actor, group_id):
    group = Group.objects.get(pk=group_id, is_deleted=False)
    configuration_edition(actor, group.edition_id, "group:update", draft_write=True)
    group.refresh_from_db()
    if group.is_deleted:
        raise BusinessError(40401, "Division not found", 404)
    if group.offering_set.filter(is_deleted=False).exists():
        raise BusinessError(
            40902, "Detach the division from all offerings before deleting it"
        )
    group.is_deleted = True
    group.deleted_at = timezone.now()
    group.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
    audit(
        actor,
        "group.deleted",
        "group",
        group.pk,
        scope={"edition_id": group.edition_id},
    )


@transaction.atomic
def change_group_state(actor, group_id, action):
    group = Group.objects.get(pk=group_id, is_deleted=False)
    edition = configuration_edition(
        actor, group.edition_id, "group:enable_disable", lock=True
    )
    group.refresh_from_db()
    if group.is_deleted:
        raise BusinessError(40401, "Division not found", 404)
    if edition.status == "closed":
        raise BusinessError(40902, "Closed editions are read-only")
    transition(group, action, CONFIGURATION_TRANSITIONS)
    group.save(update_fields=["status", "updated_at"])
    audit(
        actor,
        f"group.{group.status}",
        "group",
        group.pk,
        scope={"edition_id": edition.id},
    )
    return group

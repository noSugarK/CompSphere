from uuid import uuid4

from django.db import transaction

from apps.audit.services import audit
from apps.competitions.models import Competition, Season
from apps.rbac.services import grants, require_perm
from core.exceptions import BusinessError
from core.state import transition


def managed_competitions(user):
    queryset = Competition.objects.filter(is_deleted=False).order_by("-id")
    competition_ids = []
    for grant in grants(user):
        if "competition:read" not in grant["permissions"]:
            continue
        if grant["scope_type"] == "global" and grant["role"] == "platform_admin":
            return queryset
        if grant["scope_type"] == "competition":
            competition_ids.append(grant["scope_id"])
    if not competition_ids:
        raise BusinessError(40301, "Competition registry access is not granted", 403)
    return queryset.filter(pk__in=competition_ids)


@transaction.atomic
def create_competition(actor, data):
    """Create a private draft without assigning roles or creating an edition."""
    require_perm(actor, "competition:create")
    item = Competition.objects.create(
        public_code=f"CMP-{uuid4().hex[:24].upper()}", **data
    )
    audit(actor, "competition.created", "competition", item.id)
    return item


@transaction.atomic
def create_season(actor, data):
    require_perm(actor, "season:create")
    item = Season.objects.create(**data)
    audit(actor, "season.created", "season", item.id)
    return item


@transaction.atomic
def activate_season(actor, season_id):
    require_perm(actor, "season:activate")
    item = Season.objects.select_for_update().get(pk=season_id)
    transition(item, "activate", {("draft", "activate"): "active"})
    item.save(update_fields=["status"])
    audit(actor, "season.activated", "season", item.id)
    return item


@transaction.atomic
def set_current_season(actor, season_id):
    """Serialize switches, including when no season is currently selected."""
    require_perm(actor, "season:set_current")
    locked = list(Season.objects.select_for_update().order_by("pk"))
    item = next((season for season in locked if season.pk == season_id), None)
    if item is None:
        raise BusinessError(40401, "Season not found", 404)
    if item.status != "active":
        raise BusinessError(40902, "Only an active season may be selected")
    if item.is_default:
        return item
    previous = next((season for season in locked if season.is_default), None)
    if previous is not None:
        previous.is_default = False
        previous.save(update_fields=["is_default"])
    item.is_default = True
    item.save(update_fields=["is_default"])
    audit(
        actor,
        "season.current_changed",
        "season",
        item.id,
        detail={"previous_season_id": previous.id if previous else None},
    )
    return item

from uuid import uuid4

from django.db import transaction

from apps.audit.services import audit
from apps.competitions.models import Competition, Edition, Season
from apps.rbac.services import grants, has_perm, require_perm
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


def managed_editions(actor, competition_id):
    queryset = Edition.objects.filter(
        competition_id=competition_id, competition__is_deleted=False, is_deleted=False
    ).order_by("-year", "-edition_no", "-id")
    edition_ids = []
    for grant in grants(actor):
        if "edition:read" not in grant["permissions"]:
            continue
        if (grant["scope_type"] == "global" and grant["role"] == "platform_admin") or (
            grant["scope_type"] == "competition" and grant["scope_id"] == competition_id
        ):
            Competition.objects.get(pk=competition_id, is_deleted=False)
            return queryset
        if grant["scope_type"] == "edition":
            edition_ids.append(grant["scope_id"])
    scoped = queryset.filter(pk__in=edition_ids)
    if not scoped.exists():
        raise BusinessError(40401, "Competition not found", 404)
    return scoped


def edition_seasons(actor, competition_id):
    require_perm(actor, "edition:create", competition_id=competition_id)
    Competition.objects.get(pk=competition_id, is_deleted=False)
    allowed = ["active", "draft"] if has_perm(actor, "season:read") else ["active"]
    return Season.objects.filter(status__in=allowed).order_by("-starts_on", "-id")


@transaction.atomic
def create_edition(actor, competition_id, data):
    """Store a draft under an authorized parent; configuration does not publish it."""
    require_perm(actor, "edition:create", competition_id=competition_id)
    competition = Competition.objects.select_for_update().get(
        pk=competition_id, is_deleted=False
    )
    season = Season.objects.select_for_update().get(pk=data["season_id"])
    if competition.status == "archived" or season.status == "archived":
        raise BusinessError(
            40902, "An archived competition or season cannot accept a new edition"
        )
    if season.status == "draft" and not has_perm(actor, "season:read"):
        raise BusinessError(40401, "Season not found", 404)
    item = Edition.objects.create(competition=competition, **data)
    audit(
        actor,
        "edition.created",
        "edition",
        item.id,
        scope={"competition_id": competition.id, "season_id": season.id},
    )
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

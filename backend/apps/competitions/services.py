from uuid import uuid4

from django.db import transaction
from django.utils import timezone

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


def configuration_edition(
    actor, edition_id, permission, *, draft_write=False, lock=False
):
    editions = Edition.objects.filter(is_deleted=False, competition__is_deleted=False)
    if draft_write or lock:
        editions = editions.select_for_update(of=("self",))
    item = editions.get(pk=edition_id)
    require_perm(actor, permission, edition=item)
    if draft_write and item.status != "draft":
        raise BusinessError(
            40902, "This configuration can only change on a draft edition"
        )
    return item


@transaction.atomic
def update_edition_details(actor, edition_id, data):
    edition = configuration_edition(
        actor, edition_id, "edition:update", draft_write=True
    )
    if not data:
        return edition
    for field, value in data.items():
        setattr(edition, field, value)
    if (
        not edition.enroll_start
        < edition.enroll_end
        <= edition.start_date
        < edition.end_date
    ):
        raise BusinessError(42203, "Registration and event dates are out of order", 422)
    configurable_dates = {"enroll_start", "enroll_end", "start_date"}
    if configurable_dates.intersection(data):
        for option in edition.offerings.filter(is_deleted=False).iterator():
            start, end = option.registration_window(edition)
            if not start < end <= edition.start_date:
                raise BusinessError(
                    42203,
                    "Adjust the offering overrides before changing this schedule",
                    422,
                )
    edition.save(update_fields=[*data, "updated_at"])
    audit(
        actor,
        "edition.updated",
        "edition",
        edition.pk,
        scope={
            "competition_id": edition.competition_id,
            "season_id": edition.season_id,
        },
    )
    return edition


def edition_publication_checks(item):
    now = timezone.now()
    offerings = list(
        item.offerings.filter(
            status="enabled",
            is_deleted=False,
            event__status="enabled",
            event__is_deleted=False,
            group__status="enabled",
            group__is_deleted=False,
        ).select_related("event", "group")
    )
    return {
        "active_season": item.season.status == "active"
        and item.competition.status != "archived",
        "title_and_venue": bool(item.name.strip() and item.venue.strip()),
        "ordered_schedule": (
            item.enroll_start < item.enroll_end <= item.start_date < item.end_date
        ),
        "open_offering": any(
            start < end <= item.start_date and now < end
            for start, end in (option.registration_window(item) for option in offerings)
        ),
        "supported_rules": (
            item.approval_mode == "single"
            and item.team_entry_mode == "open"
            and all(
                not any(
                    material.get("required")
                    for material in option.event.material_requirements
                )
                and (
                    option.group.enrollment_type == "team"
                    or option.event.min_members == 1
                )
                for option in offerings
            )
        ),
    }


@transaction.atomic
def publish_edition(actor, edition_id):
    candidate = configuration_edition(actor, edition_id, "edition:publish")
    competition = Competition.objects.select_for_update().get(
        pk=candidate.competition_id, is_deleted=False
    )
    edition = configuration_edition(
        actor, edition_id, "edition:publish", draft_write=True
    )
    edition.competition = competition
    edition.season = Season.objects.select_for_update().get(pk=edition.season_id)
    if not all(edition_publication_checks(edition).values()):
        raise BusinessError(
            40902, "Complete the edition publication checklist before publishing"
        )
    transition(edition, "publish", {("draft", "publish"): "published"})
    edition.save(update_fields=["status", "updated_at"])
    audit(
        actor,
        "edition.published",
        "edition",
        edition.id,
        scope={"competition_id": competition.id, "season_id": edition.season_id},
    )
    return edition


@transaction.atomic
def publish_competition(actor, competition_id):
    require_perm(actor, "competition:publish", competition_id=competition_id)
    item = Competition.objects.select_for_update().get(
        pk=competition_id, is_deleted=False
    )
    editions = list(
        item.editions.filter(is_deleted=False, status__in=["draft", "published"])
        .select_for_update()
        .order_by("id")
    )
    seasons = (
        Season.objects.select_for_update()
        .filter(pk__in={edition.season_id for edition in editions})
        .order_by("id")
    )
    season_by_id = {season.pk: season for season in seasons}
    for edition in editions:
        edition.season = season_by_id[edition.season_id]
        edition.competition = item
    if not any(
        all(edition_publication_checks(edition).values()) for edition in editions
    ):
        raise BusinessError(
            40902,
            "Configure at least one edition with an open offering before publishing",
        )
    transition(item, "publish", {("draft", "publish"): "published"})
    item.save(update_fields=["status", "updated_at"])
    audit(actor, "competition.published", "competition", item.id)
    return item


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

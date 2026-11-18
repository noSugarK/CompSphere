from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.services import audit
from apps.competitions.models import Season
from apps.events.models import EventType
from apps.orgs.models import Organization, OrganizationMember
from apps.profiles.models import Profile
from apps.rbac.services import has_perm, org_filter, prevent_self_review, require_perm
from apps.teams.models import (
    SeasonRegistration,
    Team,
    TeamChangeRequest,
    TeamMember,
    TeamNumber,
)
from core.crypto import decrypt, encrypt
from core.exceptions import BusinessError
from core.state import transition


def member_data(membership):
    profile = membership.user.profile
    return {
        "user_id": membership.user_id,
        "real_name": profile.real_name,
        "role": membership.role,
        "school_level": profile.school_level,
        "grade": profile.grade,
    }


def season_data(item):
    return {
        "id": item.id,
        "team_id": item.team_id,
        "season_id": item.season_id,
        "status": item.status,
        "submitted_by": item.submitted_by_id,
        "reviewer_id": item.reviewer_id,
        "comment": item.comment,
    }


def team_data(item, actor):
    data = {
        "id": item.id,
        "team_code": item.team_number.code,
        "event_code": item.event_code_id,
        "name": item.name,
        "org_id": item.org_id,
        "coach_id": item.coach_id,
        "captain_id": item.captain_id,
        "approved_revision_id": item.approved_revision_id,
        "membership_version": item.membership_version,
        "status": item.status,
        "season_registrations": [
            season_data(x) for x in item.season_registrations.all()
        ],
    }
    if (
        item.coach_id == actor.id
        or item.memberships.filter(user=actor, left_at__isnull=True).exists()
        or has_perm(actor, "team:manage_members", org_id=item.org_id)
    ):
        data["members"] = [
            member_data(x)
            for x in item.memberships.filter(left_at__isnull=True).select_related(
                "user__profile"
            )
        ]
    return data


def request_data(item):
    return {
        "id": item.id,
        "request_kind": item.request_kind,
        "team_id": item.team_id,
        "org_id": item.org_id,
        "status": item.status,
        "submitted_by": item.submitted_by_id,
        "base_revision_id": item.base_revision_id,
        "base_membership_version": item.base_membership_version,
        "registration_season_id": item.registration_season_id,
        "proposal": decrypt(item.proposal_enc),
        "comment": item.comment,
    }


def teams_for(actor):
    return (
        Team.objects.filter(is_deleted=False)
        .filter(
            org_filter(actor, "team:read")
            | Q(memberships__user=actor, memberships__left_at__isnull=True)
        )
        .distinct()
        .select_related("team_number")
    )


def requests_for(actor):
    return TeamChangeRequest.objects.filter(
        Q(submitted_by=actor)
        | (
            org_filter(actor, "team:review")
            & Q(request_kind="update", status="submitted")
        )
        | (
            org_filter(actor, "team:review_create")
            & Q(request_kind="create", status="submitted")
        )
    ).distinct()


def check_season(season_id, current=True):
    season = Season.objects.get(pk=season_id)
    if season.status != "active" or (current and not season.is_default):
        raise BusinessError(40911, "Season is not open")
    return season


def validate_proposal(actor, org_id, proposal, team=None, lock=False, event_code=None):
    ids = [x["user_id"] for x in proposal["members"]]
    if lock:
        # Serialize membership changes on the student rows, including absent memberships.
        list(User.objects.select_for_update().filter(pk__in=sorted(ids)).order_by("id"))
    profiles = {
        x.user_id: x
        for x in Profile.objects.filter(
            user_id__in=ids, is_deleted=False, user__status="active"
        )
    }
    members = set(
        OrganizationMember.objects.filter(
            org_id=org_id, user_id__in=ids, left_at__isnull=True
        ).values_list("user_id", flat=True)
    )
    if (
        set(ids) != set(profiles)
        or set(ids) != members
        or any(p.person_type != "participant" for p in profiles.values())
    ):
        raise BusinessError(
            42213, "Members must be active students of this organization", 422
        )
    if (
        TeamMember.objects.filter(user_id__in=ids, left_at__isnull=True)
        .exclude(team=team)
        .exists()
    ):
        raise BusinessError(40908, "A student already belongs to another team")
    from apps.registrations.models import SeasonStudentTeamBinding

    bindings = SeasonStudentTeamBinding.objects.filter(
        user_id__in=ids,
        season__status="active",
        event_code_id=team.event_code_id if team else event_code,
    )
    if team:
        bindings = bindings.filter(event_code_id=team.event_code_id).exclude(
            current_team=team
        )
    if (not team and bindings.exists()) or (team and bindings.exists()):
        raise BusinessError(40909, "A season binding requires a platform transfer")
    coach_id = proposal["coach_id"]
    if coach_id is not None and not (
        Profile.objects.filter(
            user_id=coach_id,
            person_type="coach",
            is_deleted=False,
            user__status="active",
        ).exists()
        and OrganizationMember.objects.filter(
            org_id=org_id, user_id=coach_id, left_at__isnull=True
        ).exists()
    ):
        raise BusinessError(42208, "Coach must belong to this organization", 422)


@transaction.atomic
def create_request(actor, data):
    require_perm(
        actor,
        "team:create" if data["request_kind"] == "create" else "team:update",
        org_id=data["org_id"],
    )
    Organization.objects.get(pk=data["org_id"], status="active", is_deleted=False)
    EventType.objects.get(pk=data["event_code"])
    team = None
    if data["request_kind"] == "create":
        check_season(data["registration_season_id"])
        existing = TeamNumber.objects.filter(code=data["team_code"]).first()
        if existing and (
            existing.org_id != data["org_id"]
            or Team.objects.filter(
                team_number=existing, event_code_id=data["event_code"]
            ).exists()
        ):
            raise BusinessError(40907, "Team identity is already registered")
    else:
        team = Team.objects.select_for_update().get(
            pk=data["team_id"], is_deleted=False, status="active"
        )
        if (
            team.org_id != data["org_id"]
            or team.event_code_id != data["event_code"]
            or team.team_number.code != data["team_code"]
        ):
            raise BusinessError(40301, "Team identity cannot be changed", 403)
        if (
            team.approved_revision_id != data["base_revision_id"]
            or team.membership_version != data["base_membership_version"]
        ):
            raise BusinessError(40906, "Team version has changed")
    validate_proposal(
        actor, data["org_id"], data["proposal"], team, event_code=data["event_code"]
    )
    item = TeamChangeRequest.objects.create(
        team=team,
        org_id=data["org_id"],
        team_code=data["team_code"],
        event_code_id=data["event_code"],
        request_kind=data["request_kind"],
        registration_season_id=data.get("registration_season_id"),
        base_revision_id=data.get("base_revision_id"),
        base_membership_version=data.get("base_membership_version", 1),
        proposal_enc=encrypt(data["proposal"]),
        submitted_by=actor,
    )
    audit(
        actor, "team.request.created", "team_request", item.id, {"org_id": item.org_id}
    )
    return item


@transaction.atomic
def submit_request(actor, pk):
    item = TeamChangeRequest.objects.select_for_update().get(pk=pk, submitted_by=actor)
    require_perm(
        actor,
        "team:create" if item.request_kind == "create" else "team:update",
        org_id=item.org_id,
    )
    if item.status != "draft":
        raise BusinessError(40902, "Request is not a draft")
    validate_proposal(
        actor,
        item.org_id,
        decrypt(item.proposal_enc),
        item.team,
        event_code=item.event_code_id,
    )
    if item.request_kind == "create":
        check_season(item.registration_season_id)
    transition(item, "submit", {("draft", "submit"): "submitted"})
    item.save(update_fields=["status"])
    audit(
        actor,
        "team.request.submitted",
        "team_request",
        item.id,
        {"org_id": item.org_id},
    )
    return item


@transaction.atomic
def review_request(actor, pk, data):
    item = TeamChangeRequest.objects.select_for_update().get(pk=pk)
    require_perm(
        actor,
        "team:review_create" if item.request_kind == "create" else "team:review",
        org_id=item.org_id,
    )
    prevent_self_review(actor, item.submitted_by_id)
    if item.status != "submitted":
        raise BusinessError(40902, "Request is not awaiting review")
    if data["action"] == "approve":
        proposal = decrypt(item.proposal_enc)
        team = (
            Team.objects.select_for_update().get(pk=item.team_id)
            if item.team_id
            else None
        )
        if team and (
            team.approved_revision_id != item.base_revision_id
            or team.membership_version != item.base_membership_version
        ):
            raise BusinessError(40906, "Team version changed")
        validate_proposal(
            actor, item.org_id, proposal, team, lock=True, event_code=item.event_code_id
        )
        if not team:
            check_season(item.registration_season_id)
            number, _ = TeamNumber.objects.get_or_create(
                code=item.team_code, defaults={"org_id": item.org_id}
            )
            if number.org_id != item.org_id:
                raise BusinessError(40907, "Team code belongs to another organization")
            team = Team.objects.create(
                team_number=number,
                event_code_id=item.event_code_id,
                org_id=item.org_id,
                name=proposal["name"],
            )
            item.team = team
        else:
            TeamMember.objects.filter(team=team, left_at__isnull=True).update(
                left_at=timezone.now()
            )
            team.membership_version += 1
        team.name = proposal["name"]
        team.coach_id = proposal["coach_id"]
        team.captain_id = proposal["captain_id"]
        team.approved_revision = item
        team.save()
        TeamMember.objects.bulk_create(
            [
                TeamMember(team=team, user_id=m["user_id"], role=m["role"])
                for m in proposal["members"]
            ]
        )
        if item.request_kind == "create":
            if item.registration_season_id is None:
                raise BusinessError(40906, "Creation request has no season")
            SeasonRegistration.objects.create(
                team=team,
                season_id=item.registration_season_id,
                status="approved",
                proposal_enc=encrypt({"team_revision_id": item.id}),
                submitted_by_id=item.submitted_by_id,
                reviewer=actor,
                reviewed_at=timezone.now(),
                comment=data["comment"] or "Approved with team creation",
            )
    transition(
        item,
        data["action"],
        {
            ("submitted", "approve"): "approved",
            ("submitted", "reject"): "rejected",
            ("submitted", "return"): "returned",
        },
    )
    item.reviewer = actor
    item.reviewed_at = timezone.now()
    item.comment = data["comment"]
    item.save()
    audit(
        actor,
        "team.request." + item.status,
        "team_request",
        item.id,
        {"org_id": item.org_id},
    )
    return item


def seasons_for(actor):
    return SeasonRegistration.objects.filter(
        Q(submitted_by=actor)
        | org_filter(actor, "team:review_season_registration", field="team__org_id")
    ).distinct()


@transaction.atomic
def create_season_request(actor, data):
    team = Team.objects.select_for_update().get(
        pk=data["team_id"], is_deleted=False, status="active"
    )
    require_perm(actor, "team:request_season_registration", org_id=team.org_id)
    check_season(data["season_id"])
    return SeasonRegistration.objects.create(
        team=team,
        season_id=data["season_id"],
        submitted_by=actor,
        proposal_enc=encrypt({"team_revision_id": team.approved_revision_id}),
    )


@transaction.atomic
def act_on_season(actor, pk, data=None):
    item = (
        SeasonRegistration.objects.select_for_update().select_related("team").get(pk=pk)
    )
    if data is None:
        require_perm(actor, "team:request_season_registration", org_id=item.team.org_id)
        if item.submitted_by_id != actor.id:
            raise BusinessError(40301, "Permission denied", 403)
        if item.status != "draft":
            raise BusinessError(40902, "Request is not a draft")
        check_season(item.season_id)
        transition(item, "submit", {("draft", "submit"): "submitted"})
    else:
        require_perm(actor, "team:review_season_registration", org_id=item.team.org_id)
        prevent_self_review(actor, item.submitted_by_id)
        if item.status != "submitted":
            raise BusinessError(40902, "Request is not awaiting review")
        check_season(item.season_id, current=False)
        transition(
            item,
            data["action"],
            {("submitted", "approve"): "approved", ("submitted", "reject"): "rejected"},
        )
        item.reviewer = actor
        item.reviewed_at = timezone.now()
        item.comment = data["comment"]
    item.save()
    audit(
        actor,
        "season.team." + item.status,
        "team_season_registration",
        item.id,
        {"org_id": item.team.org_id},
    )
    return item

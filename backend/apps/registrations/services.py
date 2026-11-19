import hashlib
import json
import uuid
from collections import defaultdict

from django.db import transaction
from django.db.models import Case, Exists, F, FilteredRelation, OuterRef, Q, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.services import audit
from apps.competitions.services import published_editions
from apps.events.models import Offering
from apps.notifications.models import RegistrationNotice
from apps.notifications.services import record_registration_notice
from apps.orgs.models import OrganizationMember
from apps.profiles.models import Profile
from apps.rbac.services import (
    has_perm,
    org_filter,
    prevent_self_review,
    registration_filter,
    require_perm,
)
from apps.registrations.models import (
    ApprovalRecord,
    Registration,
    RegistrationMember,
    RegistrationSubmission,
    SeasonStudentTeamBinding,
)
from apps.teams.models import SeasonRegistration, Team, TeamMember
from apps.teams.services import member_data
from core.constants import EDITABLE_STATES, ErrorCode
from core.crypto import decrypt, encrypt
from core.exceptions import BusinessError
from core.models import IdempotencyRecord
from core.state import transition


def visible_registrations(actor, managed=False):
    own = (
        Q(submitted_by=actor)
        | Q(individual_user=actor)
        | Q(team__memberships__user=actor, team__memberships__left_at__isnull=True)
        | Q(team__coach=actor)
    )
    if not has_perm(actor, "registration:read_own", own=True):
        own &= org_filter(actor, "registration:read_own")
    queryset = Registration.objects.filter(is_deleted=False).select_related(
        "edition__season",
        "edition__competition",
        "offering__event",
        "offering__group",
        "team",
    )
    normal = (
        ~Q(edition__status="closed")
        & registration_filter(actor, "registration:read")
        & Q(current_submission_no__isnull=False)
    )
    historical = (
        Q(edition__status="closed")
        & registration_filter(actor, "registration:read_history")
        & Q(current_submission_no__isnull=False)
    )
    if managed:
        return queryset.filter(normal | historical).distinct()
    return queryset.filter(
        (own & ~Q(edition__status="closed")) | normal | historical
    ).distinct()


REVIEW_QUEUE_DIMENSIONS = {
    "edition": ("edition_id", "edition__name"),
    "event": ("frozen__offering__event_id", "frozen__offering__event__name"),
    "group": ("frozen__offering__group_id", "frozen__offering__group__name"),
    "org": ("org_id", "org__name"),
}


def review_queue(actor):
    return (
        visible_registrations(actor, managed=True)
        .annotate(
            frozen=FilteredRelation(
                "submissions",
                condition=Q(submissions__submission_no=F("current_submission_no")),
            )
        )
        .filter(frozen__isnull=False)
    )


def review_queue_items(actor, filters):
    items = review_queue(actor)
    for dimension, (id_field, _) in REVIEW_QUEUE_DIMENSIONS.items():
        if dimension in filters:
            items = items.filter(**{id_field: filters[dimension]})
    if "status" in filters:
        items = items.filter(status=filters["status"])
    if search := filters.get("q"):
        items = items.filter(
            Q(batch_no__icontains=search) | Q(team__team_number__code__icontains=search)
        )
    member = RegistrationMember.objects.filter(
        registration_id=OuterRef("pk"),
        submission_no=OuterRef("current_submission_no"),
        user_id=actor.id,
    )
    can_review = Case(
        When(
            Q(status="pending_review", edition__season__status="active")
            & ~Q(edition__status="closed")
            & ~Q(submitted_by_id=actor.id)
            & registration_filter(actor, "approval:review_single")
            & ~Exists(member),
            then=Value(True),
        ),
        default=Value(False),
    )
    return items.values(
        "id",
        "batch_no",
        "status",
        "submitted_at",
        can_review=can_review,
        submission_no=F("current_submission_no"),
        team_code=F("team__team_number__code"),
        **{
            f"{dimension}_name": F(name_field)
            for dimension, (_, name_field) in REVIEW_QUEUE_DIMENSIONS.items()
        },
    ).order_by("-id")


def review_queue_options(actor, dimension, edition=None):
    items = review_queue(actor)
    if edition is not None:
        items = items.filter(edition_id=edition)
    id_field, name_field = REVIEW_QUEUE_DIMENSIONS[dimension]
    return (
        items.annotate(option_id=F(id_field), name=F(name_field))
        .values("option_id", "name")
        .order_by("name", "option_id")
    )


def can_edit(actor, item):
    return item.submitted_by_id == actor.id and has_perm(
        actor, "registration:update", org_id=item.org_id, edition=item.edition, own=True
    )


def approval_data(record):
    return {
        "id": record.id,
        "submission_no": record.submission_no,
        "action": record.action,
        "comment": record.comment,
        "reviewer_id": record.actor_id,
        "created_at": record.created_at.isoformat(),
    }


def submission_history(item):
    return item.submissions.select_related(
        "offering__event", "offering__group"
    ).order_by("submission_no")


def attach_submitted_members(item, submissions):
    if not submissions:
        return
    by_number = defaultdict(list)
    members = RegistrationMember.objects.filter(
        registration=item,
        submission_no__in=[submission.submission_no for submission in submissions],
    ).order_by("submission_no", "sort_order", "id")
    for member in members:
        by_number[member.submission_no].append(
            dict(member.public_info, user_id=member.user_id)
        )
    for submission in submissions:
        submission.members = by_number[submission.submission_no]


def serialize_registration(item, actor):
    editable = can_edit(actor, item) and item.status in EDITABLE_STATES
    data = {
        "id": item.id,
        "batch_no": item.batch_no,
        "edition_id": item.edition_id,
        "offering_id": item.offering_id,
        "enrollment_kind": item.enrollment_kind,
        "team_id": item.team_id,
        "individual_user_id": item.individual_user_id,
        "org_id": item.org_id,
        "submitted_by": item.submitted_by_id,
        "status": item.status,
        "current_submission_no": item.current_submission_no,
        "approved_submission_no": item.approved_submission_no,
        "version": item.version,
        "selected_school_level": item.selected_school_level,
        "coach_user_id": item.coach_user_id,
        "members": [],
        "files": [],
        "approval_records": [
            approval_data(x) for x in item.approval_records.order_by("id")
        ],
        "can_edit": editable,
    }
    private = item.submitted_by_id == actor.id or has_perm(
        actor, "registration:read", org_id=item.org_id, edition=item.edition
    )
    if item.current_submission_no:
        submission = item.submissions.get(submission_no=item.current_submission_no)
        data["members"] = [
            dict(x.public_info, user_id=x.user_id)
            for x in item.submitted_members.filter(
                submission_no=item.current_submission_no
            ).order_by("sort_order", "id")
        ]
        snapshot = decrypt(submission.snapshot_enc)
        if not editable:
            for field in ("offering_id", "selected_school_level", "coach_user_id"):
                data[field] = snapshot[field]
        if private:
            data.update({k: snapshot[k] for k in ("contact", "form_data", "consents")})
    if editable or (
        not item.current_submission_no and item.submitted_by_id == actor.id
    ):
        if private:
            draft = decrypt(item.draft_enc)
            data.update({k: draft[k] for k in ("contact", "form_data", "consents")})
        if item.team_id:
            data["members"] = [
                member_data(x)
                for x in TeamMember.objects.filter(
                    team_id=item.team_id, left_at__isnull=True
                ).select_related("user__profile")
            ]
        elif item.individual_user_id:
            profile = Profile.objects.get(user_id=item.individual_user_id)
            data["members"] = [
                {
                    "user_id": item.individual_user_id,
                    "real_name": profile.real_name,
                    "role": "member",
                    "school_level": profile.school_level,
                    "grade": profile.grade,
                }
            ]
    return data


def assert_version(item, version):
    if item.version != version:
        raise BusinessError(40906, "Registration version has changed")


def assert_editor(actor, item):
    if not can_edit(actor, item):
        raise BusinessError(40301, "Permission denied", 403)


def validate_offering(offering, edition_id):
    if (
        offering.edition_id != edition_id
        or offering.event.edition_id != edition_id
        or offering.group.edition_id != edition_id
        or offering.is_deleted
        or offering.event.is_deleted
        or offering.group.is_deleted
        or offering.status != "enabled"
        or offering.event.status != "enabled"
        or offering.group.status != "enabled"
    ):
        raise BusinessError(42207, "Offering is not available", 422)


def can_register_team(actor, team):
    own = team.captain_id == actor.id or team.coach_id == actor.id
    return has_perm(actor, "registration:create", org_id=team.org_id, own=own)


def require_team_actor(actor, team):
    if not can_register_team(actor, team):
        raise BusinessError(40301, "Permission denied", 403)


def available_offerings(actor, edition_id, team_id=None):
    edition = published_editions().get(pk=edition_id, team_entry_mode="open")
    now = timezone.now()
    options = (
        edition.offerings.alias(
            effective_start=Coalesce("enroll_start", "edition__enroll_start"),
            effective_end=Coalesce("enroll_end", "edition__enroll_end"),
        )
        .filter(
            effective_start__lte=now,
            effective_end__gte=now,
            is_deleted=False,
            status="enabled",
            event__edition_id=edition.id,
            event__status="enabled",
            event__is_deleted=False,
            group__edition_id=edition.id,
            group__status="enabled",
            group__is_deleted=False,
            group__age_min__isnull=True,
            group__age_max__isnull=True,
        )
        .select_related("event", "group")
        .order_by("id")
    )
    if team_id is None:
        return edition, options
    team = Team.objects.get(pk=team_id, is_deleted=False)
    if not can_register_team(actor, team):
        raise BusinessError(40401, "Team not found", 404)
    if team.status != "active" or not team.approved_revision_id:
        raise BusinessError(42211, "Team is not approved", 422)
    if not SeasonRegistration.objects.filter(
        team=team, season_id=edition.season_id, status="approved"
    ).exists():
        raise BusinessError(40910, "Team season registration is not approved")
    return edition, options.filter(
        event__code_id=team.event_code_id, group__enrollment_type__in=["team", "both"]
    )


def lock_registration_team(actor, pk, reviewing=False):
    preliminary = Registration.objects.select_related("edition").get(
        pk=pk, is_deleted=False
    )
    if reviewing:
        require_perm(
            actor,
            "registration:read",
            org_id=preliminary.org_id,
            edition=preliminary.edition,
        )
        require_perm(
            actor,
            "approval:review_single",
            org_id=preliminary.org_id,
            edition=preliminary.edition,
        )
    else:
        assert_editor(actor, preliminary)
    if preliminary.team_id:
        Team.objects.select_for_update().get(pk=preliminary.team_id)


@transaction.atomic
def create_registration(actor, edition, data, key=None):
    create_record = None
    if data.get("submit"):
        if not isinstance(key, str) or not 8 <= len(key) <= 128:
            raise BusinessError(40001, "A valid Idempotency-Key is required", 400)
        digest = hashlib.sha256(
            json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        create_record, created = IdempotencyRecord.objects.get_or_create(
            actor=actor,
            key=key,
            action=f"registration.create:{edition.pk}",
            defaults={"request_hash": digest},
        )
        if not created:
            if create_record.request_hash != digest:
                raise BusinessError(
                    40905, "Idempotency key was used for different parameters"
                )
            saved_result = create_record.result
            if (
                not isinstance(saved_result, dict)
                or type(saved_result.get("registration_id")) is not int
            ):
                raise BusinessError(40906, "The prior operation cannot be replayed")
            item = visible_registrations(actor).get(pk=saved_result["registration_id"])
            assert_editor(actor, item)
            require_perm(
                actor,
                "registration:create",
                org_id=item.org_id,
                edition=item.edition,
                own=True,
            )
            return item
    offering = Offering.objects.select_related("event", "group", "edition").get(
        pk=data["offering_id"]
    )
    validate_offering(offering, edition.id)
    if edition.status != "published" or edition.competition.status != "published":
        raise BusinessError(40401, "Not found", 404)
    team = None
    if data["enrollment_kind"] == "team":
        team = Team.objects.select_for_update(of=("self",)).get(
            pk=data["team_id"], is_deleted=False, status="active"
        )
        require_team_actor(actor, team)
        org_id = team.org_id
    else:
        require_perm(actor, "registration:create", own=True)
        membership = OrganizationMember.objects.filter(
            user=actor,
            is_primary=True,
            left_at__isnull=True,
            org__status="active",
            org__is_deleted=False,
        ).first()
        if not membership:
            raise BusinessError(
                42213, "An approved organization membership is required", 422
            )
        org_id = membership.org_id
    if offering.group.enrollment_type not in ("both", data["enrollment_kind"]):
        raise BusinessError(42207, "Enrollment kind is not allowed", 422)
    draft = {k: data[k] for k in ("contact", "form_data", "consents")}
    item = Registration.objects.create(
        batch_no=f"REG-{edition.id}-{uuid.uuid4().hex[:8].upper()}",
        edition=edition,
        offering=offering,
        enrollment_kind=data["enrollment_kind"],
        team=team,
        individual_user=actor if not team else None,
        org_id=org_id,
        submitted_by=actor,
        coach_user_id=data["coach_user_id"],
        selected_school_level=data["selected_school_level"],
        draft_enc=encrypt(draft),
    )
    if data.get("submit"):
        if create_record is None:
            raise BusinessError(40906, "Submission was not prepared")
        item = submit_registration(
            actor, item.id, item.version, key, action="submit", request_data=data
        )
        create_record.result = {"registration_id": item.id}
        create_record.save(update_fields=["result"])
    audit(
        actor,
        "registration.created",
        "registration",
        item.id,
        {"edition_id": edition.id},
    )
    return item


@transaction.atomic
def update_registration(actor, pk, data):
    item = (
        Registration.objects.select_for_update(of=("self",))
        .select_related("edition")
        .get(pk=pk, is_deleted=False)
    )
    assert_editor(actor, item)
    assert_version(item, data["version"])
    if item.status not in EDITABLE_STATES:
        raise BusinessError(40902, "Submitted data is frozen")
    if item.edition.status == "closed":
        raise BusinessError(40902, "Edition is closed")
    draft = decrypt(item.draft_enc)
    for key in ("contact", "form_data", "consents"):
        if key in data:
            draft[key] = data[key]
    if "offering_id" in data:
        offering = Offering.objects.select_related("event", "group").get(
            pk=data["offering_id"]
        )
        validate_offering(offering, item.edition_id)
        if offering.group.enrollment_type not in ("both", item.enrollment_kind):
            raise BusinessError(42207, "Enrollment kind is not allowed", 422)
        item.offering = offering
    for key in ("coach_user_id", "selected_school_level"):
        if key in data:
            setattr(item, key, data[key])
    item.draft_enc = encrypt(draft)
    item.version += 1
    item.save()
    audit(
        actor,
        "registration.updated",
        "registration",
        item.id,
        {"edition_id": item.edition_id},
        {"version": item.version},
    )
    return item


def check_submission(item, actor):
    offering = item.offering
    edition = item.edition
    validate_offering(offering, edition.id)
    if (
        edition.status != "published"
        or edition.competition.status != "published"
        or edition.season.status != "active"
        or not edition.season.is_default
    ):
        raise BusinessError(40911, "Current active season is required")
    now = timezone.now()
    start, end = offering.registration_window(edition)
    if not start <= now <= end:
        raise BusinessError(42203, "Registration window is closed", 422)
    if edition.approval_mode != "single" or edition.team_entry_mode != "open":
        raise BusinessError(40902, "This approval or entry mode is not enabled")
    if offering.group.age_min is not None or offering.group.age_max is not None:
        raise BusinessError(42207, "Age-based enrollment is not enabled", 422)
    if (
        offering.group.school_level
        and item.selected_school_level != offering.group.school_level
    ):
        raise BusinessError(
            42205, "School level does not match the selected group", 422
        )
    draft = decrypt(item.draft_enc)
    if (
        not draft["contact"]["name"].strip()
        or not draft["contact"]["phone"].strip()
        or not draft["form_data"]["project_title"].strip()
        or not draft["consents"]["document_usage"]
    ):
        raise BusinessError(
            42202, "Required contact, project and consent data are incomplete", 422
        )
    required = [m for m in offering.event.material_requirements if m.get("required")]
    if required:
        raise BusinessError(
            42202,
            "Required materials must be uploaded through the secure material service",
            422,
        )
    if item.org.status != "active" or item.org.is_deleted:
        raise BusinessError(42213, "Organization is not active", 422)
    license_item = None
    if item.team_id:
        team = Team.objects.select_for_update(of=("self",)).get(pk=item.team_id)
        require_team_actor(actor, team)
        if team.status != "active" or not team.approved_revision_id:
            raise BusinessError(42211, "Team is not approved", 422)
        if team.event_code_id != offering.event.code_id:
            raise BusinessError(42207, "Team event does not match", 422)
        license_item = SeasonRegistration.objects.filter(
            team=team, season=edition.season, status="approved"
        ).first()
        if not license_item:
            raise BusinessError(40910, "Team season registration is not approved")
        memberships = list(
            TeamMember.objects.filter(team=team, left_at__isnull=True)
            .select_related("user__profile")
            .order_by("user_id")
        )
        members = [
            {
                "user": m.user,
                "profile": m.user.profile,
                "public": member_data(m),
                "role": m.role,
            }
            for m in memberships
        ]
    else:
        profile = Profile.objects.get(user_id=item.individual_user_id, is_deleted=False)
        members = [
            {
                "user": profile.user,
                "profile": profile,
                "public": {
                    "user_id": profile.user_id,
                    "real_name": profile.real_name,
                    "role": "member",
                    "school_level": profile.school_level,
                    "grade": profile.grade,
                },
                "role": "member",
            }
        ]
    list(
        User.objects.select_for_update(of=("self",))
        .filter(pk__in=[m["user"].id for m in members])
        .order_by("id")
    )
    if not offering.event.min_members <= len(members) <= offering.event.max_members:
        raise BusinessError(
            42201, "Team member count is outside the configured range", 422
        )
    for m in members:
        p = m["profile"]
        if (
            not m["user"].is_active
            or m["user"].must_change_password
            or not p.document_hash
        ):
            raise BusinessError(42206, "A participant profile is incomplete", 422)
        if not OrganizationMember.objects.filter(
            user=m["user"], org_id=item.org_id, left_at__isnull=True
        ).exists():
            raise BusinessError(
                42213, "A member no longer belongs to the organization", 422
            )
        if offering.group.grade_limits and p.grade not in offering.group.grade_limits:
            raise BusinessError(42204, "Grade is outside the configured range", 422)
        if (
            item.team_id
            and SeasonStudentTeamBinding.objects.filter(
                season__status="active",
                event_code_id=item.team.event_code_id,
                user=m["user"],
            )
            .exclude(current_team_id=item.team_id)
            .exists()
        ):
            raise BusinessError(40909, "A member is bound to another team")
    if offering.event.coach_required:
        if (
            not item.coach_user_id
            or not Profile.objects.filter(
                user_id=item.coach_user_id, person_type="coach", user__status="active"
            ).exists()
            or not OrganizationMember.objects.filter(
                user_id=item.coach_user_id, org_id=item.org_id, left_at__isnull=True
            ).exists()
        ):
            raise BusinessError(42208, "A valid organization coach is required", 422)
    return members, draft, license_item


@transaction.atomic
def submit_registration(actor, pk, version, key, action="submit", request_data=None):
    if not isinstance(key, str) or not 8 <= len(key) <= 128:
        raise BusinessError(40001, "A valid Idempotency-Key is required", 400)
    # Team before registration/student locks: team approval uses the same order.
    # The idempotency UNIQUE key serializes absent-row races without a user lock.
    lock_registration_team(actor, pk)
    digest = hashlib.sha256(
        json.dumps(
            request_data or {"version": version}, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    record, created = IdempotencyRecord.objects.get_or_create(
        actor=actor,
        key=key,
        action=f"registration.{action}:{pk}",
        defaults={"request_hash": digest},
    )
    item = (
        Registration.objects.select_for_update(of=("self",))
        .select_related(
            "edition__season",
            "edition__competition",
            "offering__event",
            "offering__group",
            "org",
            "team",
        )
        .get(pk=pk, is_deleted=False)
    )
    assert_editor(actor, item)
    if item.edition.status == "closed":
        raise BusinessError(40401, "Not found", 404)
    if not created:
        if record.request_hash != digest:
            raise BusinessError(
                40905, "Idempotency key was used for different parameters"
            )
        return item
    assert_version(item, version)
    if item.status not in EDITABLE_STATES:
        raise BusinessError(40902, "Registration is not editable")
    members, draft, license_item = check_submission(item, actor)
    number = (item.current_submission_no or 0) + 1
    frozen = dict(
        draft,
        offering_id=item.offering_id,
        selected_school_level=item.selected_school_level,
        coach_user_id=item.coach_user_id,
    )
    RegistrationSubmission.objects.create(
        registration=item,
        submission_no=number,
        offering_id=item.offering_id,
        team=item.team,
        team_revision_id=item.team.approved_revision_id if item.team else None,
        selected_school_level=item.selected_school_level,
        snapshot_enc=encrypt(frozen),
        submitted_by=actor,
        access_snapshot={
            "season_id": item.edition.season_id,
            "license_id": license_item.id if license_item else None,
        },
    )
    for index, m in enumerate(members):
        public = {k: v for k, v in m["public"].items() if k != "user_id"}
        RegistrationMember.objects.create(
            registration=item,
            submission_no=number,
            user=m["user"],
            snapshot_enc=encrypt(public),
            public_info=public,
            document_hash=m["profile"].document_hash,
            role=m["role"],
            sort_order=index,
        )
    transition(
        item, "submit", {(s, "submit"): "pending_review" for s in EDITABLE_STATES}
    )
    item.current_submission_no = number
    item.approved_submission_no = None
    item.submitted_at = timezone.now()
    item.version += 1
    item.save()
    record.result = {"registration_id": item.id, "submission_no": number}
    record.save(update_fields=["result"])
    audit(
        actor,
        "registration.submitted",
        "registration",
        item.id,
        {"edition_id": item.edition_id},
        {"submission_no": number},
    )
    record_registration_notice(item, number, RegistrationNotice.Kind.SUBMITTED)
    return item


@transaction.atomic
def cancel_or_withdraw(actor, pk, version, action):
    item = (
        Registration.objects.select_for_update(of=("self",))
        .select_related("edition")
        .get(pk=pk, is_deleted=False)
    )
    assert_editor(actor, item)
    assert_version(item, version)
    now = timezone.now()
    if item.edition.status != "published":
        raise BusinessError(40902, "Edition is not open")
    if action == "cancel_review":
        if item.current_submission_no is None:
            raise BusinessError(40902, "There is no submission to cancel")
        if (
            item.status != "pending_review"
            or item.approval_records.filter(
                submission_no=item.current_submission_no,
                action__in=["approve", "reject", "return"],
            ).exists()
        ):
            raise BusinessError(40906, "The current submission was already reviewed")
        item.submissions.filter(submission_no=item.current_submission_no).update(
            cancelled_at=now
        )
    else:
        start, end = item.offering.registration_window(item.edition)
        if not start <= now <= end:
            raise BusinessError(42203, "Registration window is closed", 422)
        if item.status not in ["draft", "pending_review", "returned", "rejected"]:
            raise BusinessError(40902, "This submission cannot be withdrawn")
    before = item.status
    transition(
        item,
        action,
        {
            ("pending_review", "cancel_review"): "draft",
            **{
                (state, "withdraw"): "withdrawn"
                for state in ("draft", "pending_review", "returned", "rejected")
            },
        },
    )
    item.version += 1
    item.save()
    if item.current_submission_no:
        ApprovalRecord.objects.create(
            registration=item,
            submission_no=item.current_submission_no,
            action=action,
            from_status=before,
            to_status=item.status,
            actor=actor,
        )
    audit(
        actor,
        "registration." + action,
        "registration",
        item.id,
        {"edition_id": item.edition_id},
    )
    return item


@transaction.atomic
def review_registration(actor, pk, data, *, pending_only=False):
    lock_registration_team(actor, pk, reviewing=True)
    item = (
        Registration.objects.select_for_update(of=("self",))
        .select_related(
            "edition__season",
            "edition__competition",
            "offering__event",
            "offering__group",
            "team",
        )
        .get(pk=pk, is_deleted=False)
    )
    require_perm(actor, "registration:read", org_id=item.org_id, edition=item.edition)
    require_perm(
        actor, "approval:review_single", org_id=item.org_id, edition=item.edition
    )
    number = item.current_submission_no
    if number is None:
        raise BusinessError(40902, "There is no submitted round to review")
    if item.current_submission_no != data["submission_no"]:
        raise BusinessError(40906, "Submission version has changed")
    if pending_only and item.status != "pending_review":
        raise BusinessError(
            ErrorCode.STATE, "Bulk review requires a pending submission"
        )
    member_ids = list(
        item.submitted_members.filter(submission_no=number).values_list(
            "user_id", flat=True
        )
    )
    prevent_self_review(actor, item.submitted_by_id, member_ids)
    if item.edition.status == "closed" or item.edition.season.status != "active":
        raise BusinessError(40902, "Edition or season is closed")
    if item.status == "approved":
        require_perm(
            actor, "approval:reject_approved", org_id=item.org_id, edition=item.edition
        )
    before = item.status
    transitions = {
        ("pending_review", "approve"): "approved",
        ("pending_review", "reject"): "rejected",
        ("pending_review", "return"): "returned",
        ("approved", "reject"): "rejected",
    }
    transition(item, data["action"], transitions)
    if data["action"] == "approve" and item.team is not None:
        if not SeasonRegistration.objects.filter(
            team_id=item.team.pk, season_id=item.edition.season_id, status="approved"
        ).exists():
            raise BusinessError(40910, "Team season registration is not approved")
        list(
            User.objects.select_for_update(of=("self",))
            .filter(pk__in=member_ids)
            .order_by("id")
        )
        for user_id in member_ids:
            binding, created = SeasonStudentTeamBinding.objects.get_or_create(
                season_id=item.edition.season_id,
                event_code_id=item.team.event_code_id,
                user_id=user_id,
                defaults={
                    "original_team_id": item.team_id,
                    "current_team_id": item.team_id,
                    "source_registration": item,
                    "source_submission_no": item.current_submission_no,
                },
            )
            if not created and binding.current_team_id != item.team_id:
                raise BusinessError(40909, "A member is bound to another team")
    item.approved_submission_no = (
        item.current_submission_no if item.status == "approved" else None
    )
    item.version += 1
    item.save()
    ApprovalRecord.objects.create(
        registration=item,
        submission_no=number,
        action=data["action"],
        comment=data["comment"],
        from_status=before,
        to_status=item.status,
        actor=actor,
    )
    audit(
        actor,
        "registration." + item.status,
        "registration",
        item.id,
        {"edition_id": item.edition_id},
        {"submission_no": item.current_submission_no},
    )
    record_registration_notice(item, number, item.status)
    return item


def bulk_review_registrations(actor, data):
    ids = [target["registration_id"] for target in data["items"]]
    visible_ids = set(
        visible_registrations(actor, managed=True)
        .filter(id__in=ids)
        .values_list("id", flat=True)
    )
    results = []
    for target in data["items"]:
        registration_id = target["registration_id"]
        result = {
            "registration_id": registration_id,
            "code": ErrorCode.NOT_FOUND,
            "status": None,
        }
        if registration_id in visible_ids:
            try:
                row = review_registration(
                    actor,
                    registration_id,
                    {
                        "action": data["action"],
                        "comment": data["comment"],
                        "submission_no": target["submission_no"],
                    },
                    pending_only=True,
                )
            except Registration.DoesNotExist:
                pass
            except BusinessError as error:
                result["code"] = (
                    ErrorCode.NOT_FOUND
                    if error.code == ErrorCode.FORBIDDEN
                    else error.code
                )
            else:
                result.update(code=0, status=row.status)
        results.append(result)
    return results

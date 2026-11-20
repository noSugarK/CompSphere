from django.db import transaction
from django.utils import timezone

from apps.audit.services import audit
from apps.awards.models import Award, AwardRecord, AwardRoster
from apps.competitions.models import Edition
from apps.events.models import Offering
from apps.rbac.services import require_perm
from apps.registrations.models import Registration, RegistrationMember
from core.constants import ROSTER_PUBLISH_FIELDS
from core.exceptions import BusinessError
from core.state import transition

ROSTER_TRANSITIONS = {
    ("editing", "submit"): "under_approval",
    ("under_approval", "approve"): "confirmed",
    ("under_approval", "reject"): "editing",
    ("confirmed", "unlock"): "editing",
}
# 02 §4.7: award:lock_roster only appears here; unlock is the confirmed->editing path.
DECISION_PERMISSIONS = {
    "submit": "award:submit_roster",
    "approve": "award:approve_roster",
    "reject": "award:approve_roster",
    "unlock": "award:lock_roster",
}


def managed_edition(actor, edition_id, permission, *, lock=False):
    """Scope-checked edition for award work; 404 for foreign or deleted ones."""
    editions = Edition.objects.filter(
        pk=edition_id, is_deleted=False, competition__is_deleted=False
    )
    if lock:
        editions = editions.select_for_update(of=("self",))
    edition = editions.first()
    if edition is None:
        raise BusinessError(40401, "Not found", 404)
    require_perm(actor, permission, edition=edition)
    return edition


def write_edition(actor, edition_id, permission, *, lock=False):
    edition = managed_edition(actor, edition_id, permission, lock=lock)
    if edition.status == "closed":
        raise BusinessError(40902, "Closed editions are read-only")
    return edition


def edition_offering(edition, offering_id):
    if offering_id is None:
        return None
    offering = Offering.objects.filter(
        pk=offering_id, edition=edition, is_deleted=False
    ).first()
    if offering is None:
        raise BusinessError(40401, "Not found", 404)
    return offering


@transaction.atomic
def create_award(actor, edition_id, data):
    edition = write_edition(actor, edition_id, "award:config", lock=True)
    item = Award.objects.create(
        edition=edition,
        offering=edition_offering(edition, data.get("offering_id")),
        rank_level=data["rank_level"],
        name=data["name"],
        quota=data.get("quota"),
        sort_order=data.get("sort_order", 0),
    )
    audit(actor, "award.created", "award", item.id, scope={"edition_id": edition.id})
    return item


def locked_award(actor, award_id, permission):
    edition_id = (
        Award.objects.values_list("edition_id", flat=True)
        .filter(pk=award_id, is_deleted=False)
        .first()
    )
    if edition_id is None:
        raise BusinessError(40401, "Not found", 404)
    edition = write_edition(actor, edition_id, permission, lock=True)
    return Award.objects.get(pk=award_id, is_deleted=False), edition


@transaction.atomic
def update_award(actor, award_id, data):
    item, edition = locked_award(actor, award_id, "award:config")
    if not data:
        return item
    for field, value in data.items():
        setattr(item, field, value)
    item.save(update_fields=[*data, "updated_at"])
    audit(actor, "award.updated", "award", item.pk, scope={"edition_id": edition.id})
    return item


@transaction.atomic
def delete_award(actor, award_id):
    item, edition = locked_award(actor, award_id, "award:config")
    if AwardRecord.objects.filter(award=item, is_deleted=False).exists():
        raise BusinessError(40902, "Award is used by a roster entry")
    item.is_deleted = True
    item.deleted_at = timezone.now()
    item.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
    audit(actor, "award.deleted", "award", item.pk, scope={"edition_id": edition.id})


def approved_members(submissions):
    """Real names from the frozen public_info of the awarded round only."""
    names: dict[int, list[str]] = {key: [] for key in submissions}
    rows = RegistrationMember.objects.filter(
        registration_id__in=list(submissions)
    ).order_by("registration_id", "sort_order", "id")
    for row in rows:
        if row.submission_no != submissions[row.registration_id]:
            continue
        names[row.registration_id].append(
            str((row.public_info or {}).get("real_name", ""))
        )
    return names


def team_code(registration):
    team = registration.team
    return team.team_number.code if team is not None else None


def roster_rows(roster):
    records = (
        []
        if roster is None
        else list(
            roster.records.filter(is_deleted=False)
            .select_related(
                "award", "registration__team__team_number", "registration__org"
            )
            .order_by("award__sort_order", "award_id", "id")
        )
    )
    submissions = {item.registration_id: item.submission_no for item in records}
    names = approved_members(submissions)
    return [
        {
            "registration_id": item.registration_id,
            "award_id": item.award_id,
            "submission_no": item.submission_no,
            "batch_no": item.batch_no,
            "team_code": team_code(item.registration),
            "org_name": item.registration.org.name,
            "member_names": names[item.registration_id],
            "award_name": item.award.name,
            "rank_level": item.award.rank_level,
        }
        for item in records
    ]


def roster_data(edition, roster, offering):
    return {
        "id": roster.id if roster else None,
        "edition_id": edition.id,
        "offering_id": offering.id if offering else None,
        "event_name": offering.event.name if offering else None,
        "group_name": offering.group.name if offering else None,
        "status": roster.status if roster else "editing",
        "version": roster.version if roster else 1,
        "records": roster_rows(roster),
    }


def find_roster(edition, offering_id):
    return AwardRoster.objects.filter(
        edition=edition, offering_id=offering_id, is_deleted=False
    ).first()


def list_rosters(actor, edition_id, offering_id):
    edition = managed_edition(actor, edition_id, "award:read")
    if offering_id is not None:
        offering = edition_offering(edition, offering_id)
        roster = find_roster(edition, offering.id)
        return [roster_data(edition, roster, offering)]
    scopes: list = [(None, find_roster(edition, None))]
    for offering in (
        Offering.objects.filter(edition=edition, is_deleted=False, status="enabled")
        .select_related("event", "group")
        .order_by("id")
    ):
        scopes.append((offering, find_roster(edition, offering.id)))
    return [roster_data(edition, roster, offering) for offering, roster in scopes]


@transaction.atomic
def change_records(actor, edition_id, offering_id, version, add, remove):
    edition = write_edition(actor, edition_id, "award:manage_roster", lock=True)
    offering = edition_offering(edition, offering_id)
    roster = find_roster(edition, offering.id if offering else None)
    if roster is None:
        if version != 1:
            raise BusinessError(40906, "Roster version has changed")
        roster = AwardRoster.objects.create(
            edition=edition, offering=offering, submitted_by=None
        )
    elif roster.version != version:
        raise BusinessError(40906, "Roster version has changed")
    if roster.status != "editing":
        raise BusinessError(40902, "Confirmed rosters cannot change")
    for registration_id in remove or []:
        record = roster.records.filter(
            registration_id=registration_id, is_deleted=False
        ).first()
        if record is None:
            raise BusinessError(40401, "Not found", 404)
        record.is_deleted = True
        record.deleted_at = timezone.now()
        record.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
    for target in add or []:
        award = Award.objects.filter(
            pk=target["award_id"], edition=edition, is_deleted=False
        ).first()
        if award is None or award.offering_id != (offering.id if offering else None):
            raise BusinessError(40401, "Not found", 404)
        registration = Registration.objects.filter(
            pk=target["registration_id"], edition=edition, is_deleted=False
        ).first()
        # 04 §附注：获奖只认 approved 且 approved_submission_no==current 的明确轮次。
        round_no = registration.approved_submission_no if registration else None
        if (
            registration is None
            or registration.status != "approved"
            or registration.current_submission_no != round_no
            or not round_no
        ):
            raise BusinessError(40902, "Only approved submissions can be awarded")
        if offering is not None and registration.offering_id != offering.id:
            raise BusinessError(40902, "Registration belongs to another offering")
        if roster.records.filter(registration=registration, is_deleted=False).exists():
            raise BusinessError(40901, "Registration is already awarded in this roster")
        if award.quota is not None:
            if roster.records.filter(award=award, is_deleted=False).count() >= (
                award.quota
            ):
                raise BusinessError(40902, "Award quota is full")
        AwardRecord.objects.create(
            edition=edition,
            roster=roster,
            award=award,
            registration=registration,
            submission_no=round_no,
            recipient_kind=registration.enrollment_kind,
            batch_no=registration.batch_no,
        )
    roster.save(update_fields=["updated_at"])
    audit(
        actor,
        "roster.records_changed",
        "award_roster",
        roster.id,
        scope={"edition_id": edition.id},
        detail={"added": len(add or []), "removed": len(remove or [])},
    )
    return roster_data(edition, roster, offering)


@transaction.atomic
def decide_roster(actor, edition_id, offering_id, action, version, comment):
    edition = write_edition(actor, edition_id, DECISION_PERMISSIONS[action], lock=True)
    offering = edition_offering(edition, offering_id)
    roster = find_roster(edition, offering.id if offering else None)
    if roster is None:
        raise BusinessError(40902, "This roster has no entries yet")
    if roster.version != version:
        raise BusinessError(40906, "Roster version has changed")
    if action in ("reject", "unlock") and not (comment or "").strip():
        raise BusinessError(40001, "A reason is required", 400)
    if action == "submit" and not roster.records.filter(is_deleted=False).exists():
        raise BusinessError(40902, "An empty roster cannot be submitted")
    transition(roster, action, ROSTER_TRANSITIONS)
    fields = ["status", "updated_at"]
    if action == "submit":
        roster.submitted_by = actor
        fields.append("submitted_by")
    elif action == "approve":
        roster.approved_by = actor
        roster.approved_at = timezone.now()
        fields += ["approved_by", "approved_at"]
    elif action == "unlock":
        # 03 §5：解锁重新编辑递增版本，旧异步回调必须失效（证书作废前置属里程碑 2）。
        roster.version += 1
        roster.lock_note = comment
        roster.approved_by = None
        roster.approved_at = None
        fields += ["version", "lock_note", "approved_by", "approved_at"]
    roster.save(update_fields=fields)
    event = {
        "approve": "roster.confirmed",
        "unlock": "roster.unlocked",
    }.get(action, f"roster.{action}")
    audit(
        actor,
        event,
        "award_roster",
        roster.id,
        scope={"edition_id": edition.id},
        detail={"version": roster.version, "comment": comment or ""},
    )
    return roster_data(edition, roster, offering)


def edition_info(edition):
    return {
        "id": edition.id,
        "name": edition.name,
        "status": edition.status,
        "roster_publication": edition.roster_publication,
        "roster_publish_fields": sorted(set(edition.roster_publish_fields)),
        "roster_published_at": (
            edition.roster_published_at.isoformat()
            if edition.roster_published_at
            else None
        ),
    }


@transaction.atomic
def set_publication(actor, edition_id, data):
    edition = write_edition(actor, edition_id, "roster:publish", lock=True)
    # 02 §4.5/§4.7: intersect before storing, so the DB never holds a leaking list.
    edition.roster_publication = data["roster_publication"]
    edition.roster_publish_fields = sorted(
        set(data["roster_publish_fields"]) & ROSTER_PUBLISH_FIELDS
    )
    edition.save(
        update_fields=[
            "roster_publication",
            "roster_publish_fields",
            "updated_at",
        ]
    )
    audit(
        actor,
        "roster.publication_updated",
        "edition",
        edition.id,
        scope={"edition_id": edition.id},
        detail={
            "mode": edition.roster_publication,
            "fields": edition.roster_publish_fields,
        },
    )
    return edition


@transaction.atomic
def publish_roster(actor, edition_id, action):
    permission = "roster:publish" if action == "publish" else "roster:unpublish"
    edition = write_edition(actor, edition_id, permission, lock=True)
    if action == "publish":
        # 03 §9: only a published edition with a non-none mode can go live.
        if edition.status != "published" or edition.roster_publication == "none":
            raise BusinessError(40902, "Publication is not available for this edition")
        edition.roster_published_at = timezone.now()
    else:
        edition.roster_published_at = None
    edition.save(update_fields=["roster_published_at", "updated_at"])
    audit(
        actor,
        "roster.published" if action == "publish" else "roster.unpublished",
        "edition",
        edition.id,
        scope={"edition_id": edition.id},
    )
    return edition


def public_roster(request, edition_id, event_id, group_id):
    """02 §4.7 in fixed order, never the management serializer:
    edition+timestamp -> mode -> login -> field intersection -> confirmed only."""
    edition = Edition.objects.filter(
        pk=edition_id,
        is_deleted=False,
        status="published",
        competition__status="published",
        competition__is_deleted=False,
        roster_published_at__isnull=False,
    ).first()
    if edition is None or edition.roster_publication == "none":
        raise BusinessError(40401, "Not found", 404)
    if edition.roster_publication == "login" and not getattr(
        request.user, "is_authenticated", False
    ):
        raise BusinessError(40101, "Sign in to view this roster", 401)
    allowed = ROSTER_PUBLISH_FIELDS & set(edition.roster_publish_fields)
    # 队卡上的赛项/组别取报名自身冻结的组合，通用奖条目因此同样可公示。
    records = list(
        AwardRecord.objects.filter(
            edition=edition, roster__status="confirmed", is_deleted=False
        )
        .select_related(
            "award",
            "registration__team__team_number",
            "registration__org",
            "registration__offering__event",
            "registration__offering__group",
        )
        .order_by("award__sort_order", "award_id", "id")
    )
    names = approved_members(
        {item.registration_id: item.submission_no for item in records}
    )
    entries: list[dict] = []
    for item in records:
        offering = item.registration.offering
        if event_id is not None and offering.event_id != event_id:
            continue
        if group_id is not None and offering.group_id != group_id:
            continue
        row = {
            "team_code": team_code(item.registration),
            "org_name": item.registration.org.name,
            "event": offering.event.name,
            "group": offering.group.name,
            "member_names": names[item.registration_id],
            "award": item.award.name,
        }
        entries.append({key: value for key, value in row.items() if key in allowed})
    return {
        "edition_id": edition.id,
        "edition_name": edition.name,
        "publish_fields": sorted(allowed),
        "entries": entries,
    }

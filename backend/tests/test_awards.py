from django.utils import timezone
from rest_framework.test import APIClient

from apps.competitions.models import Edition
from apps.events.models import Offering
from apps.groups.models import Group
from apps.registrations.models import Registration


def create_award(client, edition_id, payload):
    return client.post(f"/api/v1/editions/{edition_id}/awards", payload, format="json")


def roster_put(client, edition_id, offering_id, body, action="records"):
    url = f"/api/v1/editions/{edition_id}/roster/{action}"
    if offering_id is not None:
        url += f"?offering_id={offering_id}"
    return client.put(url, body, format="json")


def roster_action(client, edition_id, offering_id, action, body):
    url = f"/api/v1/editions/{edition_id}/roster/{action}"
    if offering_id is not None:
        url += f"?offering_id={offering_id}"
    return client.post(url, body, format="json")


def test_roster_lock_and_unlock_cycle(dataset, actor_client, approved_registration):
    edition = dataset["edition"]
    offering = dataset["offering"]
    organizer = actor_client(dataset["accounts"]["organizer"])

    created = create_award(
        organizer,
        edition.id,
        {
            "offering_id": offering.id,
            "rank_level": "first",
            "name": "一等奖",
            "quota": 1,
        },
    )
    assert created.status_code == 201, created.data
    award_id = created.data["data"]["id"]

    added = roster_put(
        organizer,
        edition.id,
        offering.id,
        {
            "version": 1,
            "add": [{"registration_id": approved_registration, "award_id": award_id}],
        },
    )
    assert added.status_code == 200, added.data
    roster = added.data["data"]
    assert roster["status"] == "editing" and roster["version"] == 1
    (record,) = roster["records"]
    assert record["submission_no"] == 1 and record["member_names"]
    assert record["team_code"] == dataset["team"].team_number.code

    # same registration twice -> roster-level uniqueness
    duplicate = roster_put(
        organizer,
        edition.id,
        offering.id,
        {
            "version": 1,
            "add": [{"registration_id": approved_registration, "award_id": award_id}],
        },
    )
    assert duplicate.data["code"] == 40901

    submitted = roster_action(
        organizer, edition.id, offering.id, "submit", {"version": 1}
    ).data["data"]
    assert submitted["status"] == "under_approval"

    confirmed = roster_action(
        organizer, edition.id, offering.id, "approve", {"version": 1}
    ).data["data"]
    assert confirmed["status"] == "confirmed"

    # 03 §5: confirmed locks entries and the state machine alike.
    locked = roster_put(
        organizer,
        edition.id,
        offering.id,
        {"version": 1, "remove": [approved_registration]},
    )
    assert locked.data["code"] == 40902
    resubmit = roster_action(
        organizer, edition.id, offering.id, "submit", {"version": 1}
    )
    assert resubmit.data["code"] == 40902

    # reviewer holds no award:* permission (02 §award rows).
    reviewer = actor_client(dataset["accounts"]["reviewer"])
    denied = roster_put(reviewer, edition.id, offering.id, {"version": 1, "remove": []})
    assert denied.data["code"] == 40301

    blank_unlock = roster_action(
        organizer,
        edition.id,
        offering.id,
        "unlock",
        {"version": 1, "comment": " "},
    )
    assert blank_unlock.data["code"] == 40001
    unlocked = roster_action(
        organizer,
        edition.id,
        offering.id,
        "unlock",
        {"version": 1, "comment": "Fix entry"},
    ).data["data"]
    assert unlocked["status"] == "editing" and unlocked["version"] == 2
    # old callbacks against the frozen version must fail (04 §award_rosters.version)
    stale = roster_put(
        organizer,
        edition.id,
        offering.id,
        {"version": 1, "remove": [approved_registration]},
    )
    assert stale.data["code"] == 40906


def test_award_scope_mismatch_is_hidden(dataset, actor_client, approved_registration):
    edition = dataset["edition"]
    offering = dataset["offering"]
    organizer = actor_client(dataset["accounts"]["organizer"])
    general = create_award(
        organizer, edition.id, {"rank_level": "custom", "name": "组委会奖"}
    ).data["data"]["id"]
    # 06: 越权与不存在统一 40401 —— award from another roster scope reads as missing.
    mismatch = roster_put(
        organizer,
        edition.id,
        offering.id,
        {
            "version": 1,
            "add": [{"registration_id": approved_registration, "award_id": general}],
        },
    )
    assert mismatch.data["code"] == 40401
    # the edition-general roster accepts the general award (01 §奖项通用档).
    general_row = roster_put(
        organizer,
        edition.id,
        None,
        {
            "version": 1,
            "add": [{"registration_id": approved_registration, "award_id": general}],
        },
    ).data["data"]
    assert [row["award_id"] for row in general_row["records"]] == [general]
    assert general_row["offering_id"] is None


def test_roster_entry_requires_current_approved_round(
    dataset, actor_client, approved_registration
):
    edition = dataset["edition"]
    offering = dataset["offering"]
    organizer = actor_client(dataset["accounts"]["organizer"])
    award_id = create_award(
        organizer,
        edition.id,
        {"offering_id": offering.id, "rank_level": "third", "name": "三等奖"},
    ).data["data"]["id"]
    registration = Registration.objects.get(pk=approved_registration)

    # approved but a newer round has been submitted -> approved != current
    registration.current_submission_no = 2
    registration.save(update_fields=["current_submission_no"])
    stale_round = roster_put(
        organizer,
        edition.id,
        offering.id,
        {
            "version": 1,
            "add": [{"registration_id": registration.id, "award_id": award_id}],
        },
    )
    assert stale_round.data["code"] == 40902

    # not approved at all
    registration.current_submission_no = 1
    registration.status = "pending_review"
    registration.approved_submission_no = None
    registration.save()
    not_approved = roster_put(
        organizer,
        edition.id,
        offering.id,
        {
            "version": 1,
            "add": [{"registration_id": registration.id, "award_id": award_id}],
        },
    )
    assert not_approved.data["code"] == 40902
    assert not registration.awards.filter(is_deleted=False).exists()


def test_award_quota_soft_limit(
    dataset, actor_client, draft_payload, approved_registration
):
    edition = dataset["edition"]
    offering = dataset["offering"]
    student = actor_client(dataset["accounts"]["student"])
    organizer = actor_client(dataset["accounts"]["organizer"])
    # second approved registration for the same team in another open combination
    second_group = Group.objects.create(
        edition=edition, code="MS", name="初中组", enrollment_type="both"
    )
    second_offering = Offering.objects.create(
        edition=edition, event=offering.event, group=second_group
    )
    created = student.post(
        f"/api/v1/editions/{edition.id}/registrations",
        {
            **draft_payload,
            "offering_id": second_offering.id,
            "submit": False,
        },
        format="json",
    ).data["data"]
    student.post(
        f"/api/v1/registrations/{created['id']}/submit",
        {"version": created["version"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="quota-two",
    )
    approved = organizer.post(
        f"/api/v1/registrations/{created['id']}/approval",
        {"action": "approve", "comment": "", "submission_no": 1},
        format="json",
    )
    assert approved.status_code == 200, approved.data

    # edition-general award with quota=1 served by the general roster
    award_id = create_award(
        organizer,
        edition.id,
        {"rank_level": "excellence", "name": "优秀组织奖", "quota": 1},
    ).data["data"]["id"]
    first = roster_put(
        organizer,
        edition.id,
        None,
        {
            "version": 1,
            "add": [{"registration_id": approved_registration, "award_id": award_id}],
        },
    )
    assert first.status_code == 200, first.data
    over = roster_put(
        organizer,
        edition.id,
        None,
        {
            "version": 1,
            "add": [{"registration_id": created["id"], "award_id": award_id}],
        },
    )
    assert over.data["code"] == 40902


def test_public_roster_visibility_order(dataset, actor_client, approved_registration):
    edition = dataset["edition"]
    offering = dataset["offering"]
    organizer = actor_client(dataset["accounts"]["organizer"])
    anonymous = APIClient()
    url = f"/api/v1/public/editions/{edition.id}/roster"

    award_id = create_award(
        organizer,
        edition.id,
        {"offering_id": offering.id, "rank_level": "first", "name": "一等奖"},
    ).data["data"]["id"]
    roster_put(
        organizer,
        edition.id,
        offering.id,
        {
            "version": 1,
            "add": [{"registration_id": approved_registration, "award_id": award_id}],
        },
    )
    for action in ("submit", "approve"):
        roster_action(organizer, edition.id, offering.id, action, {"version": 1})

    # 1) published edition without roster_published_at -> 404 (not 403).
    assert anonymous.get(url).status_code == 404
    assert anonymous.get(url).data["code"] == 40401

    patched = organizer.patch(
        f"/api/v1/editions/{edition.id}/roster-publication",
        {
            "roster_publication": "open",
            "roster_publish_fields": [
                "team_code",
                "org_name",
                "member_names",
                "event",
                "group",
                "award",
                "contact_name",  # not in PUBLIC_ALLOWED -> dropped at save time
            ],
        },
        format="json",
    ).data["data"]
    assert "contact_name" not in patched["roster_publish_fields"]
    published = organizer.post(
        f"/api/v1/editions/{edition.id}/roster/publish", {}, format="json"
    ).data["data"]
    assert published["roster_published_at"]

    body = anonymous.get(url).data["data"]
    (entry,) = body["entries"]
    assert set(entry) == {
        "team_code",
        "org_name",
        "member_names",
        "event",
        "group",
        "award",
    }
    registration = Registration.objects.get(pk=approved_registration)
    assert entry["team_code"] == registration.team.team_number.code
    assert "contact_name" not in str(body)
    assert (registration.contact_phone or "@@") not in str(body)

    # frozen-offering filters
    assert anonymous.get(url, {"event": offering.event_id}).data["data"]["entries"]
    assert not anonymous.get(url, {"event": 99999}).data["data"]["entries"]

    # 3) login mode: anonymous 401, any logged-in account 200.
    organizer.patch(
        f"/api/v1/editions/{edition.id}/roster-publication",
        {
            "roster_publication": "login",
            "roster_publish_fields": ["team_code", "award"],
        },
        format="json",
    )
    gated = anonymous.get(url)
    assert gated.status_code == 401 and gated.data["code"] == 40101
    student = actor_client(dataset["accounts"]["student"])
    rows = student.get(url).data["data"]
    assert rows["publish_fields"] == ["award", "team_code"]
    (entry,) = rows["entries"]
    assert set(entry) == {"team_code", "award"}

    # none mode -> 404; unpublish -> immediate 404.
    organizer.patch(
        f"/api/v1/editions/{edition.id}/roster-publication",
        {"roster_publication": "none", "roster_publish_fields": ["team_code"]},
        format="json",
    )
    assert anonymous.get(url).data["code"] == 40401
    organizer.patch(
        f"/api/v1/editions/{edition.id}/roster-publication",
        {"roster_publication": "open", "roster_publish_fields": ["team_code"]},
        format="json",
    )
    organizer.post(f"/api/v1/editions/{edition.id}/roster/unpublish", {}, format="json")
    assert anonymous.get(url).data["code"] == 40401


def test_locked_roster_blocks_approved_reject(
    dataset, actor_client, approved_registration
):
    offering = dataset["offering"]
    organizer = actor_client(dataset["accounts"]["organizer"])
    award_id = create_award(
        organizer,
        offering.edition_id,
        {"offering_id": offering.id, "rank_level": "first", "name": "一等奖"},
    ).data["data"]["id"]
    roster_put(
        organizer,
        offering.edition_id,
        offering.id,
        {
            "version": 1,
            "add": [{"registration_id": approved_registration, "award_id": award_id}],
        },
    )
    for action in ("submit", "approve"):
        roster_action(
            organizer, offering.edition_id, offering.id, action, {"version": 1}
        )
    # 03 §4：名单已确认时先解锁，才能驳回已通过报名。
    blocked = organizer.post(
        f"/api/v1/registrations/{approved_registration}/approval",
        {"action": "reject", "comment": "Late change", "submission_no": 1},
        format="json",
    )
    assert blocked.data["code"] == 40902
    roster_action(
        organizer,
        offering.edition_id,
        offering.id,
        "unlock",
        {"version": 1, "comment": "Re-review result"},
    )
    allowed = organizer.post(
        f"/api/v1/registrations/{approved_registration}/approval",
        {"action": "reject", "comment": "Late change", "submission_no": 1},
        format="json",
    )
    assert allowed.status_code == 200, allowed.data


def test_closed_edition_and_cross_scope(dataset, actor_client, approved_registration):
    edition = dataset["edition"]
    organizer = actor_client(dataset["accounts"]["organizer"])
    manager = actor_client(dataset["accounts"]["manager"])
    # org_admin has no award permissions at all.
    assert (
        create_award(manager, edition.id, {"rank_level": "first", "name": "x"}).data[
            "code"
        ]
        == 40301
    )
    assert manager.get(f"/api/v1/editions/{edition.id}/rosters").data["code"] == 40301
    # closed edition freezes writes (03 §4).
    Edition.objects.filter(pk=edition.id).update(status="closed")
    blocked = create_award(
        organizer, edition.id, {"rank_level": "first", "name": "一等奖"}
    )
    assert blocked.data["code"] == 40902
    # public page under a closed edition: 404 even with a stale timestamp.
    Edition.objects.filter(pk=edition.id).update(roster_published_at=timezone.now())
    assert (
        APIClient().get(f"/api/v1/public/editions/{edition.id}/roster").status_code
        == 404
    )

from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.competitions.models import Competition, Edition
from apps.events.models import Event, Offering
from apps.groups.models import Group


@pytest.fixture
def draft_edition(dataset):
    existing = dataset["edition"]
    return Edition.objects.create(
        competition_id=existing.competition_id,
        season_id=existing.season_id,
        name="Event configuration draft",
        year=existing.year,
        edition_no=2,
        enroll_start=existing.enroll_start,
        enroll_end=existing.enroll_end,
        start_date=existing.start_date,
        end_date=existing.end_date,
    )


@pytest.mark.django_db
def test_draft_edition_updates_keep_identity_and_offering_windows(
    dataset, actor_client, draft_edition
):
    platform = actor_client(dataset["accounts"]["platform"])
    organizer = actor_client(dataset["accounts"]["organizer"])
    endpoint = f"/api/v1/editions/{draft_edition.id}"
    assert (
        organizer.patch(endpoint, {"name": "Forbidden"}, format="json").status_code
        == 403
    )
    assert (
        platform.patch(
            endpoint, {"season_id": draft_edition.season_id}, format="json"
        ).status_code
        == 400
    )
    assert (
        platform.patch(
            endpoint,
            {"enroll_start": draft_edition.enroll_end.isoformat()},
            format="json",
        ).status_code
        == 422
    )
    event = Event.objects.create(edition=draft_edition, code_id="VURC", name="VURC")
    division = Group.objects.create(edition=draft_edition, code="U", name="University")
    Offering.objects.create(
        edition=draft_edition,
        event=event,
        group=division,
        enroll_end=draft_edition.start_date,
    )
    earlier = draft_edition.start_date - timedelta(minutes=1)
    assert (
        platform.patch(
            endpoint, {"start_date": earlier.isoformat()}, format="json"
        ).status_code
        == 422
    )
    response = platform.patch(
        endpoint, {"name": "Revised edition", "venue": "New venue"}, format="json"
    )
    assert response.status_code == 200, response.data
    assert response.data["data"]["name"] == "Revised edition"
    assert response.data["data"]["season_id"] == draft_edition.season_id
    assert AuditLog.objects.filter(
        action="edition.updated", resource_id=str(draft_edition.id)
    ).exists()
    published_url = f"/api/v1/editions/{dataset['edition'].id}"
    assert (
        platform.patch(published_url, {"name": "Rejected"}, format="json").status_code
        == 409
    )


@pytest.mark.django_db
def test_event_registry_uses_stable_types_and_locks_published_rules(
    dataset, actor_client, draft_edition
):
    existing = dataset["edition"]
    draft = draft_edition
    platform = actor_client(dataset["accounts"]["platform"])
    organizer = actor_client(dataset["accounts"]["organizer"])
    detail = f"/api/v1/editions/{draft.id}"
    endpoint = f"{detail}/events"
    payload = {
        "event_code": "VURC",
        "name": "Synthetic event",
        "min_members": 2,
        "max_members": 3,
        "coach_required": False,
    }
    assert organizer.get(detail).status_code == 403
    assert platform.get(detail).data["data"]["status"] == "draft"
    assert organizer.get(endpoint).status_code == 403
    assert organizer.post(endpoint, payload, format="json").status_code == 403
    choices = platform.get(f"{detail}/event-types").data["data"]["items"]
    assert {item["code"] for item in choices} >= {
        "VURC",
        "V5RC",
        "VIQRC",
        "VAIMRC",
        "VGORC",
    }
    assert (
        platform.post(
            endpoint, {**payload, "max_members": 1}, format="json"
        ).status_code
        == 400
    )
    assert (
        platform.post(
            endpoint, {**payload, "coach_required": "false"}, format="json"
        ).status_code
        == 400
    )
    assert (
        platform.post(
            endpoint, {**payload, "event_code": "UNKNOWN"}, format="json"
        ).status_code
        == 404
    )
    created = platform.post(endpoint, payload, format="json")
    assert created.status_code == 201, created.data
    assert platform.get(endpoint).data["data"]["items"] == [created.data["data"]]
    assert platform.post(endpoint, payload, format="json").status_code == 409
    assert (
        organizer.post(
            f"/api/v1/editions/{existing.id}/events", payload, format="json"
        ).status_code
        == 409
    )
    assert AuditLog.objects.filter(
        action="event.created", resource_id=str(created.data["data"]["id"])
    ).exists()


@pytest.mark.django_db
def test_event_rule_edits_stay_in_drafts_and_state_controls_public_availability(
    dataset, actor_client, draft_edition
):
    platform = actor_client(dataset["accounts"]["platform"])
    organizer = actor_client(dataset["accounts"]["organizer"])
    event = Event.objects.create(
        edition=draft_edition,
        code_id="VURC",
        name="Draft event",
        min_members=2,
        max_members=4,
    )
    detail = f"/api/v1/events/{event.pk}"
    assert (
        organizer.patch(detail, {"name": "Outside"}, format="json").status_code == 403
    )
    assert (
        platform.patch(detail, {"event_code": "V5RC"}, format="json").status_code == 400
    )
    assert platform.patch(detail, {"max_members": 1}, format="json").status_code == 400
    updated = platform.patch(
        detail, {"max_members": 5, "coach_required": False}, format="json"
    )
    assert updated.status_code == 200, updated.data
    assert updated.data["data"]["max_members"] == 5
    division = Group.objects.create(edition=draft_edition, code="U", name="University")
    Offering.objects.create(edition=draft_edition, event=event, group=division)
    assert platform.delete(detail).status_code == 409
    assert organizer.post(f"{detail}/disable", {}, format="json").status_code == 403

    existing = dataset["offering"].event
    published = f"/api/v1/events/{existing.pk}"
    portal = f"/api/v1/public/editions/{existing.edition_id}"
    assert (
        organizer.patch(published, {"min_members": 2}, format="json").status_code == 409
    )
    assert organizer.post(f"{published}/disable", {}, format="json").status_code == 200
    assert not platform.get(portal).data["data"]["offerings"][0]["is_enabled"]
    assert organizer.post(f"{published}/enable", {}, format="json").status_code == 200
    assert platform.get(portal).data["data"]["offerings"][0]["is_enabled"]
    existing.edition.status = "closed"
    existing.edition.save(update_fields=["status"])
    assert organizer.post(f"{published}/disable", {}, format="json").status_code == 409


@pytest.mark.django_db
def test_group_crud_and_enable_disable_are_scoped(dataset, actor_client, draft_edition):
    platform = actor_client(dataset["accounts"]["platform"])
    organizer = actor_client(dataset["accounts"]["organizer"])
    student = actor_client(dataset["accounts"]["student"])
    endpoint = f"/api/v1/editions/{draft_edition.id}/groups"
    payload = {
        "code": "UNIV",
        "name": "University",
        "school_level": "U",
        "enrollment_type": "team",
        "grade_limits": ["Year 1"],
    }
    assert organizer.get(endpoint).status_code == 403
    assert organizer.post(endpoint, payload, format="json").status_code == 403
    assert student.get(endpoint).status_code == 403
    for fields in (
        {"age_min": 18},
        {"grade_limits": [1]},
        {"grade_limits": ["Year 1", " Year 1 "]},
    ):
        assert (
            platform.post(endpoint, {**payload, **fields}, format="json").status_code
            == 400
        )
    result = platform.post(endpoint, payload, format="json")
    assert result.status_code == 201, result.data
    group = result.data["data"]
    detail = f"/api/v1/groups/{group['id']}"
    assert platform.get(endpoint).data["data"]["items"] == [group]
    assert organizer.patch(detail, {"name": "Other"}, format="json").status_code == 403
    assert (
        platform.patch(detail, {"grade_limits": []}, format="json").data["data"][
            "grade_limits"
        ]
        == []
    )
    assert (
        platform.post(f"{detail}/disable", {}, format="json").data["data"]["status"]
        == "disabled"
    )
    assert platform.post(f"{detail}/disable", {}, format="json").status_code == 409
    assert (
        platform.post(f"{detail}/enable", {}, format="json").data["data"]["status"]
        == "enabled"
    )
    assert platform.delete(detail).status_code == 200
    assert Group.objects.get(pk=group["id"]).is_deleted
    assert platform.get(endpoint).data["data"]["items"] == []
    assert AuditLog.objects.filter(
        action="group.deleted", resource_id=str(group["id"])
    ).exists()


@pytest.mark.django_db
def test_existing_group_can_close_registration_without_overwriting_rules(
    dataset, actor_client
):
    organizer = actor_client(dataset["accounts"]["organizer"])
    group = dataset["offering"].group
    detail = f"/api/v1/groups/{group.pk}"
    portal = f"/api/v1/public/editions/{group.edition_id}"
    assert (
        organizer.patch(
            detail, {"grade_limits": ["Other grade"]}, format="json"
        ).status_code
        == 409
    )
    assert organizer.delete(detail).status_code == 409
    assert organizer.post(f"{detail}/disable", {}, format="json").status_code == 200
    assert not organizer.get(portal).data["data"]["offerings"][0]["is_enabled"]
    assert organizer.post(f"{detail}/enable", {}, format="json").status_code == 200
    assert organizer.get(portal).data["data"]["offerings"][0]["is_enabled"]
    group.edition.status = "closed"
    group.edition.save(update_fields=["status"])
    assert organizer.post(f"{detail}/disable", {}, format="json").status_code == 409


@pytest.mark.django_db
def test_offerings_require_same_edition_and_only_open_selected_cell(
    dataset, actor_client, draft_edition
):
    student = actor_client(dataset["accounts"]["student"])
    platform = actor_client(dataset["accounts"]["platform"])
    organizer = actor_client(dataset["accounts"]["organizer"])
    event = Event.objects.create(edition=draft_edition, code_id="VURC", name="VURC")
    university = Group.objects.create(
        edition=draft_edition, code="U", name="University", school_level="U"
    )
    Group.objects.create(
        edition=draft_edition, code="ES", name="Elementary", school_level="ES"
    )
    endpoint = f"/api/v1/editions/{draft_edition.id}/offerings"
    payload = {"event_id": event.id, "group_id": university.id}
    assert organizer.post(endpoint, payload, format="json").status_code == 403
    assert student.get(endpoint).status_code == 403
    assert (
        platform.post(
            endpoint,
            {**payload, "group_id": dataset["offering"].group_id},
            format="json",
        ).status_code
        == 404
    )
    created = platform.post(endpoint, payload, format="json")
    assert created.status_code == 201, created.data
    combination = created.data["data"]
    assert platform.get(endpoint).data["data"]["items"] == [combination]
    assert platform.post(endpoint, payload, format="json").status_code == 409
    detail = f"/api/v1/offerings/{combination['id']}"
    later_start = (draft_edition.enroll_start + timedelta(hours=1)).isoformat()
    changes = {"enroll_start": later_start, "quota": 30}
    assert organizer.patch(detail, changes, format="json").status_code == 403
    assert (
        platform.patch(
            detail, {"enroll_start": "2026-11-19T12:00"}, format="json"
        ).status_code
        == 400
    )
    assert platform.patch(detail, {"quota": -1}, format="json").status_code == 400
    assert (
        platform.patch(
            detail, {"enroll_end": draft_edition.end_date.isoformat()}, format="json"
        ).status_code
        == 422
    )
    local_start = draft_edition.enroll_start.astimezone(ZoneInfo("Asia/Shanghai"))
    updated = platform.patch(
        detail,
        {
            "enroll_start": local_start.replace(tzinfo=None).isoformat(),
            "time_zone": "Asia/Shanghai",
            "quota": 30,
        },
        format="json",
    )
    assert updated.status_code == 200, updated.data
    assert updated.data["data"]["enroll_end"] is None
    assert updated.data["data"]["quota"] == 30
    assert (
        platform.patch(detail, {"enroll_start": None}, format="json").data["data"][
            "enroll_start"
        ]
        is None
    )
    assert platform.delete(f"/api/v1/groups/{university.id}").status_code == 409
    assert organizer.delete(detail).status_code == 403
    assert platform.delete(detail).data["data"] is None
    assert platform.get(endpoint).data["data"]["items"] == []
    assert (
        platform.post(endpoint, payload, format="json").data["data"]["id"]
        == combination["id"]
    )

    draft_edition.status = "published"
    draft_edition.save(update_fields=["status"])
    public_url = f"/api/v1/public/editions/{draft_edition.id}"
    offerings = student.get(public_url).data["data"]["offerings"]
    assert [(option["school_level"], option["is_enabled"]) for option in offerings] == [
        ("U", True)
    ]
    assert platform.delete(detail).status_code == 409
    assert platform.patch(detail, changes, format="json").status_code == 409
    assert offerings[0]["quota"] is None
    assert platform.post(f"{detail}/disable", {}, format="json").status_code == 200
    assert not student.get(public_url).data["data"]["offerings"][0]["is_enabled"]
    assert (
        platform.post(
            f"/api/v1/groups/{university.id}/disable", {}, format="json"
        ).status_code
        == 200
    )
    assert platform.post(f"{detail}/enable", {}, format="json").status_code == 409


@pytest.mark.django_db
def test_offering_disabling_keeps_existing_registration_readable(
    dataset, actor_client, draft_payload
):
    student = actor_client(dataset["accounts"]["student"])
    organizer = actor_client(dataset["accounts"]["organizer"])
    edition = dataset["edition"]
    registration_url = f"/api/v1/editions/{edition.id}/registrations"
    draft = student.post(registration_url, draft_payload, format="json").data["data"]
    reg_url = f"/api/v1/registrations/{draft['id']}"
    offering = dataset["offering"]
    offering.quota = 0
    offering.enroll_start = timezone.now() + timedelta(hours=1)
    offering.save(update_fields=["quota", "enroll_start"])
    blocked = student.post(
        f"{reg_url}/submit",
        {"version": draft["version"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="offering-future-window",
    )
    assert blocked.status_code == 422 and blocked.data["code"] == 42203
    offering.enroll_start = None
    offering.save(update_fields=["enroll_start"])
    assert (
        student.post(
            f"{reg_url}/submit",
            {"version": draft["version"]},
            format="json",
            HTTP_IDEMPOTENCY_KEY="offering-test",
        ).status_code
        == 200
    )
    assert (
        organizer.post(
            f"/api/v1/offerings/{dataset['offering'].id}/disable", {}, format="json"
        ).status_code
        == 200
    )
    blocked = student.post(registration_url, draft_payload, format="json")
    assert blocked.status_code == 422 and blocked.data["code"] == 42207
    assert student.get(reg_url).data["data"]["status"] == "pending_review"


@pytest.mark.django_db
def test_publication_requires_open_offering_and_both_publication_states(
    dataset, actor_client, draft_edition
):
    platform = actor_client(dataset["accounts"]["platform"])
    organizer = actor_client(dataset["accounts"]["organizer"])
    public = APIClient()
    competition = Competition.objects.create(
        public_code="QA-PUBLICATION", name="Publication QA"
    )
    draft_edition.competition = competition
    draft_edition.venue = "QA Venue"
    draft_edition.save(update_fields=["competition", "venue"])
    endpoint = f"/api/v1/editions/{draft_edition.id}"
    competition_publish = f"/api/v1/competitions/{competition.id}/publish"
    public_edition = f"/api/v1/public/editions/{draft_edition.id}"
    assert organizer.get(f"{endpoint}/publication-checks").status_code == 403
    assert organizer.post(f"{endpoint}/publish", {}, format="json").status_code == 403
    assert platform.post(competition_publish, {}, format="json").status_code == 409
    assert platform.post(f"{endpoint}/publish", {}, format="json").status_code == 409

    event = Event.objects.create(
        edition=draft_edition,
        code_id="VURC",
        name="VURC",
        material_requirements=[{"key": "student_proof", "required": True}],
    )
    division = Group.objects.create(
        edition=draft_edition, code="U", name="University", school_level="U"
    )
    cutoff = timezone.now() - timedelta(minutes=1)
    offering = Offering.objects.create(
        edition=draft_edition, event=event, group=division, enroll_end=cutoff
    )
    assert not platform.get(f"{endpoint}/publication-checks").data["data"][
        "open_offering"
    ]
    assert platform.post(f"{endpoint}/publish", {}, format="json").status_code == 409
    offering.enroll_end = draft_edition.enroll_end - timedelta(minutes=1)
    offering.save(update_fields=["enroll_end"])
    checks = platform.get(f"{endpoint}/publication-checks").data["data"]
    assert checks["open_offering"] and not checks["supported_rules"]
    assert platform.post(f"{endpoint}/publish", {}, format="json").status_code == 409
    event.material_requirements = []
    event.save(update_fields=["material_requirements"])
    assert all(platform.get(f"{endpoint}/publication-checks").data["data"].values())
    assert (
        platform.post(f"{endpoint}/publish", {}, format="json").data["data"]["status"]
        == "published"
    )
    assert public.get(public_edition).status_code == 404
    assert organizer.post(competition_publish, {}, format="json").status_code == 403
    assert (
        platform.post(competition_publish, {}, format="json").data["data"]["status"]
        == "published"
    )
    offerings = public.get(public_edition).data["data"]["offerings"]
    assert offerings[0]["enroll_start"] == draft_edition.enroll_start.isoformat()
    assert offerings[0]["enroll_end"] == offering.enroll_end.isoformat()
    assert [(item["event_code"], item["school_level"]) for item in offerings] == [
        ("VURC", "U")
    ]
    assert platform.post(f"{endpoint}/publish", {}, format="json").status_code == 409
    assert AuditLog.objects.filter(
        action="edition.published", resource_id=str(draft_edition.id)
    ).exists()
    assert AuditLog.objects.filter(
        action="competition.published", resource_id=str(competition.id)
    ).exists()

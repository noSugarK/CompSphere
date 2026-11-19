import pytest

from apps.audit.models import AuditLog
from apps.competitions.models import Edition
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

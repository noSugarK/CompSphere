import pytest

from apps.audit.models import AuditLog
from apps.competitions.models import Edition


@pytest.mark.django_db
def test_event_registry_uses_stable_types_and_locks_published_rules(
    dataset, actor_client
):
    existing = dataset["edition"]
    draft = Edition.objects.create(
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

from datetime import timedelta

import pytest

from apps.audit.models import AuditLog
from apps.competitions.models import Edition, Season
from apps.events.models import Event, Offering
from apps.groups.models import Group
from apps.registrations.models import Registration


@pytest.fixture
def side_season(dataset):
    base = Season.objects.get(pk=dataset["edition"].season_id)
    return Season.objects.create(
        code="QA-ARCHIVE",
        name="Archive QA season",
        starts_on=base.starts_on + timedelta(days=730),
        ends_on=base.ends_on + timedelta(days=730),
        status="active",
    )


def edition_copy(source, **overrides):
    payload = {
        "competition_id": source.competition_id,
        "season_id": source.season_id,
        "year": source.year,
        "edition_no": 90,
        "name": "Archive QA edition",
        "enroll_start": source.enroll_start,
        "enroll_end": source.enroll_end,
        "start_date": source.start_date,
        "end_date": source.end_date,
        "venue": "QA venue",
    }
    payload.update(overrides)
    return Edition.objects.create(**payload)


@pytest.mark.django_db
def test_season_edit_is_platform_only_and_keeps_identity(dataset, actor_client):
    platform = actor_client(dataset["accounts"]["platform"])
    organizer = actor_client(dataset["accounts"]["organizer"])
    endpoint = "/api/v1/seasons"
    created = platform.post(
        endpoint,
        {
            "code": "QA-EDIT",
            "name": "Editable season",
            "start_date": "2029-09-01",
            "end_date": "2030-08-31",
        },
        format="json",
    ).data["data"]
    url = f"{endpoint}/{created['id']}"
    assert organizer.patch(url, {"name": "Nope"}, format="json").status_code == 403
    assert platform.patch(url, {"code": "QA-HACK"}, format="json").status_code == 400
    assert platform.patch(url, {}, format="json").status_code == 200
    assert (
        platform.patch(
            url,
            {"name": "Renamed season", "end_date": "2029-01-01"},
            format="json",
        ).status_code
        == 422
    )
    renamed = platform.patch(
        url,
        {"name": "Renamed season", "start_date": "2029-09-02"},
        format="json",
    ).data["data"]
    assert renamed["name"] == "Renamed season"
    assert renamed["start_date"] == "2029-09-02"
    assert renamed["code"] == "QA-EDIT" and renamed["status"] == "draft"
    assert AuditLog.objects.filter(
        action="season.updated", resource_id=str(created["id"])
    ).exists()

    assert platform.post(f"{url}/activate", {}, format="json").status_code == 200
    assert (
        platform.post(f"{url}/archive", {}, format="json").data["data"]["status"]
        == "archived"
    )
    assert platform.patch(url, {"name": "Frozen"}, format="json").status_code == 409
    assert platform.post(f"{url}/archive", {}, format="json").status_code == 409


@pytest.mark.django_db
def test_season_archive_requires_closed_editions_and_no_pending_review(
    dataset, actor_client, side_season
):
    platform = actor_client(dataset["accounts"]["platform"])
    url = f"/api/v1/seasons/{side_season.id}"
    draft = edition_copy(
        dataset["edition"], season_id=side_season.id, status="published"
    )
    assert platform.post(f"{url}/archive", {}, format="json").status_code == 409
    draft.status = "closed"
    draft.save(update_fields=["status"])

    # the QA registration must reuse the side edition's own offering chain
    draft_event = Event.objects.create(
        edition=draft,
        code=dataset["offering"].event.code,
        name="Archive QA event",
    )
    draft_group = Group.objects.create(
        edition=draft, code="HS", name="高中组", enrollment_type="both"
    )
    draft_offering = Offering.objects.create(
        edition=draft, event=draft_event, group=draft_group
    )
    Registration.objects.create(
        batch_no="QA-ARCHIVE-PENDING",
        edition=draft,
        offering=draft_offering,
        enrollment_kind="individual",
        individual_user=dataset["accounts"]["student"],
        org=dataset["team"].org,
        submitted_by=dataset["accounts"]["student"],
        status="pending_review",
    )
    assert platform.post(f"{url}/archive", {}, format="json").status_code == 409
    # clear the pending review; withdrawn keeps PG round-reference FKs idle
    Registration.objects.update(status="withdrawn")
    assert (
        platform.post(f"{url}/archive", {}, format="json").data["data"]["status"]
        == "archived"
    )
    assert AuditLog.objects.filter(
        action="season.archived", resource_id=str(side_season.id)
    ).exists()


@pytest.mark.django_db
def test_current_season_cannot_be_archived(dataset, actor_client):
    platform = actor_client(dataset["accounts"]["platform"])
    current = Season.objects.get(pk=dataset["edition"].season_id)
    assert current.is_default
    assert (
        platform.post(
            f"/api/v1/seasons/{current.id}/archive", {}, format="json"
        ).status_code
        == 409
    )

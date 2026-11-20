from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.competitions.models import Competition, Edition
from apps.rbac.models import Role, UserRole
from apps.registrations.models import Registration


@pytest.mark.django_db
def test_competition_detail_and_edit_are_scoped(dataset, actor_client):
    platform = actor_client(dataset["accounts"]["platform"])
    outsider = actor_client(dataset["accounts"]["outsider"])
    created = platform.post(
        "/api/v1/competitions",
        {"name": "Detail QA", "summary": "Synthetic"},
        format="json",
    ).data["data"]
    url = f"/api/v1/competitions/{created['id']}"
    assert outsider.get(url).status_code == 403
    assert platform.get(url).data["data"] == {
        **created,
        "category": None,
        "level": None,
    }
    assert platform.patch(url, {"cover_url": "x"}, format="json").status_code == 400
    assert (
        platform.patch(url, {"category": "esports"}, format="json").status_code == 400
    )
    updated = platform.patch(
        url,
        {
            "name": "Detail QA renamed",
            "category": "technology",
            "level": "province",
        },
        format="json",
    ).data["data"]
    assert updated["name"] == "Detail QA renamed"
    assert updated["category"] == "technology" and updated["level"] == "province"
    assert updated["status"] == "draft"
    assert updated["public_code"] == created["public_code"]
    assert (
        platform.patch(url, {"category": None}, format="json").data["data"]["category"]
        is None
    )
    assert AuditLog.objects.filter(
        action="competition.updated", resource_id=str(created["id"])
    ).exists()

    organizer = dataset["accounts"]["organizer"]
    UserRole.objects.create(
        user=organizer,
        role=Role.objects.get(code="competition_admin"),
        scope_type="competition",
        scope_id=created["id"],
    )
    scoped = actor_client(organizer)
    assert scoped.get(url).status_code == 200
    assert (
        scoped.patch(url, {"name": "Scoped rename"}, format="json").status_code == 200
    )
    other = platform.post(
        "/api/v1/competitions", {"name": "Other", "summary": ""}, format="json"
    ).data["data"]
    assert (
        scoped.patch(
            f"/api/v1/competitions/{other['id']}", {"name": "X"}, format="json"
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_competition_archive_blocks_open_registration_and_review(dataset, actor_client):
    platform = actor_client(dataset["accounts"]["platform"])
    competition = Competition.objects.get(pk=dataset["competition"].id)
    url = f"/api/v1/competitions/{competition.id}"
    assert platform.post(f"{url}/archive", {}, format="json").status_code == 409

    now = timezone.now()
    Edition.objects.filter(pk=dataset["edition"].id).update(
        status="closed", enroll_end=now - timedelta(days=1)
    )
    Registration.objects.create(
        batch_no="QA-COMP-PENDING",
        edition_id=dataset["edition"].id,
        offering=dataset["offering"],
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

    unarchive = f"{url}/unarchive"
    assert platform.post(unarchive, {}, format="json").status_code == 400
    restored = platform.post(unarchive, {"reason": "Pilot rollback"}, format="json")
    assert restored.data["data"]["status"] == "published"
    assert AuditLog.objects.filter(
        action="competition.unarchived",
        resource_id=str(competition.id),
        detail__reason="Pilot rollback",
    ).exists()
    assert platform.post(url + "/publish", {}, format="json").status_code == 409


@pytest.mark.django_db
def test_competition_unarchive_is_platform_only(dataset, actor_client):
    competition = dataset["competition"]
    competition.status = "archived"
    competition.save(update_fields=["status"])
    url = f"/api/v1/competitions/{competition.id}/unarchive"
    organizer = dataset["accounts"]["organizer"]
    UserRole.objects.create(
        user=organizer,
        role=Role.objects.get(code="competition_admin"),
        scope_type="competition",
        scope_id=competition.id,
    )
    scoped = actor_client(organizer)
    assert scoped.post(url, {"reason": "please"}, format="json").status_code == 403
    public = APIClient()
    assert public.post(url, {"reason": "x"}, format="json").status_code == 401
    assert Competition.objects.get(pk=competition.id).status == "archived"

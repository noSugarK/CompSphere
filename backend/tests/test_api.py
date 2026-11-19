import copy
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.competitions.models import Competition, Edition, Season
from apps.events.models import Event, Offering
from apps.groups.models import Group
from apps.notifications.models import AsyncOutbox, RegistrationNotice
from apps.notifications.services import REGISTRATION_MAIL_TOPIC
from apps.notifications.tasks import dispatch_registration_mail
from apps.rbac.models import Role, UserRole
from apps.registrations.models import (
    Registration,
    RegistrationSubmission,
)
from core.crypto import decrypt


def create_draft(actor_client, dataset, payload, actor="student"):
    client = actor_client(dataset["accounts"][actor])
    response = client.post(
        f"/api/v1/editions/{dataset['edition'].id}/registrations",
        payload,
        format="json",
    )
    assert response.status_code == 201, response.data
    return client, response.data["data"]


def submit(client, draft, key="test-idempotency-key"):
    return client.post(
        f"/api/v1/registrations/{draft['id']}/submit",
        {"version": draft["version"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


@pytest.mark.django_db
def test_platform_season_lifecycle_preserves_previous_season(dataset, actor_client):
    platform = actor_client(dataset["accounts"]["platform"])
    student = actor_client(dataset["accounts"]["student"])
    seasons = "/api/v1/seasons"
    payload = {
        "code": "QA-NEXT",
        "name": "Next season",
        "start_date": "2027-09-01",
        "end_date": "2028-08-31",
    }
    assert student.get(seasons).status_code == 403
    assert student.post(seasons, payload, format="json").status_code == 403
    assert (
        platform.post(
            seasons, {**payload, "end_date": "2026-08-01"}, format="json"
        ).status_code
        == 400
    )
    assert (
        platform.post(
            seasons, {**payload, "is_default": True}, format="json"
        ).status_code
        == 400
    )

    created = platform.post(seasons, payload, format="json")
    assert created.status_code == 201, created.data
    draft = created.data["data"]
    assert draft["status"] == "draft" and not draft["is_default"]
    assert platform.post(seasons, payload, format="json").status_code == 409
    assert platform.get(seasons).data["data"]["items"][0] == draft
    activate = f"{seasons}/{draft['id']}/activate"
    switch = f"{seasons}/{draft['id']}/set-current"
    assert platform.post(switch, {}, format="json").status_code == 409
    assert student.post(activate, {}, format="json").status_code == 403
    active = platform.post(activate, {}, format="json").data["data"]
    assert active["status"] == "active" and not active["is_default"]
    assert platform.post(activate, {}, format="json").status_code == 409
    assert student.post(switch, {}, format="json").status_code == 403
    assert platform.post(switch, {}, format="json").data["data"]["is_default"]
    assert platform.post(switch, {}, format="json").status_code == 200
    assert AuditLog.objects.filter(action="season.current_changed").count() == 1

    previous = Season.objects.get(pk=dataset["edition"].season_id)
    assert previous.status == "active" and not previous.is_default
    public = APIClient()
    assert public.get(f"{seasons}/current").data["data"]["id"] == draft["id"]
    assert public.get("/api/v1/public/competitions").data["data"]["total"] == 0


@pytest.mark.django_db
def test_competition_registry_creates_private_draft_and_enforces_scope(
    dataset, actor_client
):
    accounts = dataset["accounts"]
    endpoint = "/api/v1/competitions"
    payload = {"name": "New competition", "summary": "Synthetic draft"}
    platform = actor_client(accounts["platform"])
    organizer = actor_client(accounts["organizer"])
    student = actor_client(accounts["student"])
    assert student.get(endpoint).status_code == 403
    assert organizer.get(endpoint).status_code == 403
    assert organizer.post(endpoint, payload, format="json").status_code == 403
    assert (
        platform.post(
            endpoint, {**payload, "status": "published"}, format="json"
        ).status_code
        == 400
    )
    assert (
        platform.post(endpoint, {**payload, "name": "  "}, format="json").status_code
        == 400
    )

    created = platform.post(endpoint, payload, format="json")
    assert created.status_code == 201, created.data
    draft = created.data["data"]
    assert draft["status"] == "draft" and draft["public_code"].startswith("CMP-")
    assert draft["name"] == payload["name"]
    assert not Competition.objects.get(pk=draft["id"]).editions.exists()
    assert AuditLog.objects.filter(
        actor=accounts["platform"],
        action="competition.created",
        resource_id=str(draft["id"]),
    ).exists()
    assert platform.get(endpoint).data["data"]["items"][0] == draft

    competition_id = dataset["edition"].competition_id
    UserRole.objects.create(
        user=accounts["organizer"],
        role=Role.objects.get(code="competition_admin"),
        scope_type="competition",
        scope_id=competition_id,
    )
    visible = organizer.get(endpoint).data["data"]["items"]
    assert [item["id"] for item in visible] == [competition_id]
    assert organizer.post(endpoint, payload, format="json").status_code == 403
    public = APIClient().get("/api/v1/public/competitions").data["data"]["items"]
    assert draft["id"] not in {item["id"] for item in public}


@pytest.mark.django_db
def test_edition_creation_is_scoped_and_requires_ordered_offset_times(
    dataset, actor_client
):
    existing = dataset["edition"]
    endpoint = f"/api/v1/competitions/{existing.competition_id}/editions"
    payload = {
        "season_id": existing.season_id,
        "year": 2027,
        "edition_no": 2,
        "name": "Synthetic next edition",
        "venue": "Synthetic venue",
        "enroll_start": "2027-01-01T09:00:00+08:00",
        "enroll_end": "2027-01-15T09:00:00+08:00",
        "start_date": "2027-02-01T09:00:00+08:00",
        "end_date": "2027-02-01T17:00:00+08:00",
    }
    organizer_user = dataset["accounts"]["organizer"]
    organizer = actor_client(organizer_user)
    student = actor_client(dataset["accounts"]["student"])
    assert student.get(endpoint).status_code == 404
    assert student.post(endpoint, payload, format="json").status_code == 403
    assert [item["id"] for item in organizer.get(endpoint).data["data"]["items"]] == [
        existing.id
    ]
    assert organizer.post(endpoint, payload, format="json").status_code == 403

    grant = UserRole.objects.create(
        user=organizer_user,
        role=Role.objects.get(code="competition_admin"),
        scope_type="competition",
        scope_id=existing.competition_id,
    )
    for fields in (
        {"start_date": "2027-02-01T09:00:00"},
        {"enroll_end": "2027-02-01T09:00:01+08:00"},
        {"status": "published"},
    ):
        assert (
            organizer.post(endpoint, {**payload, **fields}, format="json").status_code
            == 400
        )
    other = Competition.objects.create(
        public_code="CROSS-SCOPE", name="Other competition"
    )
    assert (
        organizer.post(
            f"/api/v1/competitions/{other.id}/editions", payload, format="json"
        ).status_code
        == 403
    )

    created = organizer.post(endpoint, payload, format="json")
    assert created.status_code == 201, created.data
    draft = created.data["data"]
    assert draft["status"] == "draft" and draft["season_id"] == existing.season_id
    assert Edition.objects.get(pk=draft["id"]).approval_mode == "single"
    assert organizer.post(endpoint, payload, format="json").status_code == 409
    assert organizer.get(endpoint).data["data"]["items"][0] == draft
    assert APIClient().get(f"/api/v1/public/editions/{draft['id']}").status_code == 404
    assert AuditLog.objects.filter(
        action="edition.created", resource_id=str(draft["id"])
    ).exists()
    choices = f"/api/v1/competitions/{existing.competition_id}/edition-seasons"
    assert organizer.get(choices).data["data"]["items"][0]["id"] == existing.season_id
    local = {**payload, "edition_no": 3, "time_zone": "Asia/Shanghai"}
    for field in ("enroll_start", "enroll_end", "start_date", "end_date"):
        local[field] = payload[field].removesuffix("+08:00")
    assert (
        organizer.post(
            endpoint, {**local, "time_zone": "America/New_York"}, format="json"
        ).status_code
        == 400
    )
    local_created = organizer.post(endpoint, local, format="json")
    assert local_created.status_code == 201, local_created.data
    assert local_created.data["data"]["start_date"] == "2027-02-01T01:00:00Z"
    grant.delete()
    assert organizer.get(choices).status_code == 403
    assert [item["id"] for item in organizer.get(endpoint).data["data"]["items"]] == [
        existing.id
    ]


@pytest.mark.django_db
def test_login_me_and_strict_unknown(dataset):
    client = APIClient()
    assert client.get("/api/v1/me").status_code == 401
    response = client.post(
        "/api/v1/auth/login",
        {
            "login_type": "email",
            "email": "student@dev.example",
            "password": "Synthetic-flow-test-2026!",
        },
        format="json",
    )
    assert response.status_code == 200, response.data
    assert response.cookies["refresh"]["httponly"]
    assert response.cookies["refresh"]["samesite"] == "Strict"
    assert "refresh" not in response.data["data"]
    client.credentials(HTTP_AUTHORIZATION="Bearer " + response.data["data"]["access"])
    me = client.get("/api/v1/me")
    assert me.data["data"]["user"]["id"] == dataset["accounts"]["student"].id
    assert "document_hash" not in str(me.data)
    bad = client.patch(
        "/api/v1/me/preferences",
        {"theme": "dark", "role": "platform_admin"},
        format="json",
    )
    assert bad.status_code == 400 and bad.data["code"] == 40001


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field,value",
    [
        ("offering_id", True),
        ("offering_id", "1"),
        ("coach_user_id", False),
        ("submit", "true"),
        ("selected_school_level", 123),
        ("status", "approved"),
    ],
)
def test_request_runtime_type_and_unknown_fields(
    dataset, actor_client, draft_payload, field, value
):
    payload = dict(draft_payload)
    payload[field] = value
    response = actor_client(dataset["accounts"]["student"]).post(
        f"/api/v1/editions/{dataset['edition'].id}/registrations",
        payload,
        format="json",
    )
    assert response.status_code == 400, response.data
    assert response.data["code"] == 40001


@pytest.mark.django_db
def test_nested_runtime_validation(dataset, actor_client, draft_payload):
    payload = copy.deepcopy(draft_payload)
    payload["contact"]["phone"] = 123
    response = actor_client(dataset["accounts"]["student"]).post(
        f"/api/v1/editions/{dataset['edition'].id}/registrations",
        payload,
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_complete_submission_return_resubmit_approve(
    dataset, actor_client, draft_payload
):
    client, draft = create_draft(actor_client, dataset, draft_payload)
    result = submit(client, draft)
    assert result.status_code == 200, result.data
    submitted = result.data["data"]
    assert (
        submitted["status"] == "pending_review"
        and submitted["current_submission_no"] == 1
    )
    assert not submitted["can_edit"]
    frozen = client.patch(
        f"/api/v1/registrations/{draft['id']}",
        {"version": submitted["version"], "form_data": {"project_title": "tamper"}},
        format="json",
    )
    assert frozen.status_code == 409 and frozen.data["code"] == 40902
    reviewer = actor_client(dataset["accounts"]["reviewer"])
    returned = reviewer.post(
        f"/api/v1/registrations/{draft['id']}/approval",
        {
            "action": "return",
            "comment": "Please correct project title",
            "submission_no": 1,
        },
        format="json",
    )
    assert returned.status_code == 200, returned.data
    updated = client.patch(
        f"/api/v1/registrations/{draft['id']}",
        {
            "version": returned.data["data"]["version"],
            "form_data": {"project_title": "Corrected title"},
        },
        format="json",
    )
    assert updated.status_code == 200, updated.data
    second = client.post(
        f"/api/v1/registrations/{draft['id']}/resubmit",
        {"version": updated.data["data"]["version"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="second-round-key",
    )
    assert second.status_code == 200, second.data
    approved = reviewer.post(
        f"/api/v1/registrations/{draft['id']}/approval",
        {"action": "approve", "comment": "", "submission_no": 2},
        format="json",
    )
    assert approved.status_code == 200, approved.data
    assert approved.data["data"]["status"] == "approved"
    assert (
        RegistrationSubmission.objects.filter(registration_id=draft["id"]).count() == 2
    )
    first = RegistrationSubmission.objects.get(
        registration_id=draft["id"], submission_no=1
    )
    assert (
        decrypt(first.snapshot_enc)["form_data"]["project_title"] == "Synthetic project"
    )
    dispatch_registration_mail()
    assert sorted(message.subject for message in mail.outbox) == sorted(
        [
            "竞云｜报名已提交",
            "竞云｜报名已提交",
            "竞云｜报名已退回修改",
            "竞云｜报名审核通过",
        ]
    )
    assert all(
        message.to == [dataset["accounts"]["student"].email]
        and message.body.endswith("http://testserver/notifications")
        and "Please correct project title" not in message.body
        for message in mail.outbox
    )


@pytest.mark.django_db
def test_registration_mail_retries_with_stable_id_and_queued_locale(
    dataset, actor_client, draft_payload
):
    student = dataset["accounts"]["student"]
    student.locale = "en-US"
    student.save(update_fields=["locale"])
    client, draft = create_draft(actor_client, dataset, draft_payload)
    assert submit(client, draft).status_code == 200
    assert submit(client, draft).status_code == 200
    row = AsyncOutbox.objects.get(topic=REGISTRATION_MAIL_TOPIC)
    assert row.payload == {
        "notice_id": RegistrationNotice.objects.get().pk,
        "locale": "en-US",
    }
    student.locale = "zh-CN"
    student.save(update_fields=["locale"])
    with patch("django.core.mail.EmailMessage.send", autospec=True) as send:
        send.return_value = 0
        dispatch_registration_mail()
        first_message = send.call_args.args[0]
    row.refresh_from_db()
    assert row.attempts == 1 and row.status == "pending" and row.lease_until is None
    assert row.next_attempt_at > timezone.now()
    AsyncOutbox.objects.filter(pk=row.pk).update(next_attempt_at=timezone.now())
    dispatch_registration_mail()
    dispatch_registration_mail()
    row.refresh_from_db()
    assert row.attempts == 2 and row.status == "dispatched"
    (delivered,) = mail.outbox
    assert delivered.subject == "CompSphere | Registration submitted"
    assert delivered.to == [student.email]
    assert (
        delivered.extra_headers["Message-ID"]
        == first_message.extra_headers["Message-ID"]
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "ineligible", ["no_email", "unverified", "reverified", "closed"]
)
def test_ineligible_registration_mail_is_not_sent(
    dataset, actor_client, draft_payload, ineligible
):
    student = dataset["accounts"]["student"]
    if ineligible == "no_email":
        student.email = None
        student.email_verified_at = None
        student.save(update_fields=["email", "email_verified_at"])
    client, draft = create_draft(actor_client, dataset, draft_payload)
    assert submit(client, draft).status_code == 200
    assert RegistrationNotice.objects.filter(recipient=student).exists()
    rows = AsyncOutbox.objects.filter(topic=REGISTRATION_MAIL_TOPIC)
    if ineligible == "no_email":
        assert not rows.exists()
    elif ineligible == "closed":
        edition = dataset["edition"]
        edition.status = "closed"
        edition.save(update_fields=["status"])
    else:
        student.email = "different@example.test"
        student.email_verified_at = (
            rows.get().created_at + timedelta(seconds=1)
            if ineligible == "reverified"
            else None
        )
        student.save(update_fields=["email", "email_verified_at"])
    dispatch_registration_mail()
    assert not getattr(mail, "outbox", [])
    assert not rows.exclude(status="dispatched").exists()


@pytest.mark.django_db
def test_idempotency_replay_and_revocation(dataset, actor_client, draft_payload):
    client, draft = create_draft(actor_client, dataset, draft_payload)
    first = submit(client, draft)
    assert first.status_code == 200, first.data
    repeated = submit(client, draft)
    assert repeated.status_code == 200
    assert RegistrationSubmission.objects.count() == 1
    mismatch = submit(client, {**draft, "version": 99})
    assert mismatch.status_code == 409 and mismatch.data["code"] == 40905
    UserRole.objects.filter(user=dataset["accounts"]["student"]).delete()
    denied = submit(client, draft)
    assert denied.status_code == 403
    assert client.get(f"/api/v1/registrations/{draft['id']}").status_code == 404


@pytest.mark.django_db
def test_registration_inbox_is_private_and_read_is_idempotent(
    dataset, actor_client, draft_payload
):
    client, draft = create_draft(actor_client, dataset, draft_payload)
    reviewer = actor_client(dataset["accounts"]["reviewer"])
    inbox_url = "/api/v1/me/notifications"
    assert APIClient().get(inbox_url).status_code == 401
    assert client.get(inbox_url).data["data"]["total"] == 0
    assert submit(client, draft).status_code == 200
    assert submit(client, draft).status_code == 200

    result = reviewer.post(
        f"/api/v1/registrations/{draft['id']}/approval",
        {"action": "return", "comment": "Private review comment", "submission_no": 1},
        format="json",
    )
    assert result.status_code == 200, result.data
    inbox_page = client.get(f"{inbox_url}?page_size=1").data["data"]
    assert inbox_page["total"] == 2
    (returned,) = inbox_page["items"]
    assert returned["kind"] == "returned"
    assert returned["registration_id"] == draft["id"]
    assert returned["submission_no"] == 1 and returned["read_at"] is None
    assert "Private review comment" not in str(returned)
    (submitted,) = client.get(f"{inbox_url}?page_size=1&page=2").data["data"]["items"]
    assert submitted["kind"] == "submitted"

    read_url = f"{inbox_url}/{returned['id']}/read"
    assert reviewer.get(inbox_url).data["data"]["total"] == 0
    unauthorized = reviewer.post(read_url, {}, format="json")
    assert unauthorized.status_code == 404 and unauthorized.data["code"] == 40401
    assert client.post(read_url, {"read_at": None}, format="json").status_code == 400
    marked = client.post(read_url, {}, format="json")
    assert marked.status_code == 200 and marked.data["data"]["read_at"]
    assert client.post(read_url, {}, format="json").data["data"] == marked.data["data"]
    assert client.get(inbox_url).data["data"]["items"][0] == marked.data["data"]

    edition = dataset["edition"]
    edition.status = "closed"
    edition.save(update_fields=["status"])
    assert client.get(inbox_url).data["data"]["total"] == 0
    assert client.post(read_url, {}, format="json").status_code == 404


@pytest.mark.django_db
def test_create_and_submit_idempotent(dataset, actor_client, draft_payload):
    client = actor_client(dataset["accounts"]["student"])
    payload = {**draft_payload, "submit": True}
    for _ in range(2):
        result = client.post(
            f"/api/v1/editions/{dataset['edition'].id}/registrations",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="create-submit-key",
        )
        assert result.status_code == 201, result.data
    assert Registration.objects.count() == 1
    assert RegistrationSubmission.objects.count() == 1


@pytest.mark.django_db
def test_cross_scope_and_self_review(dataset, actor_client, draft_payload):
    client, draft = create_draft(actor_client, dataset, draft_payload)
    assert submit(client, draft).status_code == 200
    outsider = actor_client(dataset["accounts"]["outsider"])
    assert outsider.get(f"/api/v1/registrations/{draft['id']}").status_code == 404
    assert (
        outsider.post(
            f"/api/v1/registrations/{draft['id']}/approval",
            {"action": "approve", "comment": "", "submission_no": 1},
            format="json",
        ).status_code
        == 403
    )
    UserRole.objects.create(
        user=dataset["accounts"]["student"],
        role=Role.objects.get(code="reviewer"),
        scope_type="edition",
        scope_id=dataset["edition"].id,
    )
    self_review = client.post(
        f"/api/v1/registrations/{draft['id']}/approval",
        {"action": "approve", "comment": "", "submission_no": 1},
        format="json",
    )
    assert self_review.status_code == 403 and self_review.data["code"] == 40303
    (row,) = client.get("/api/v1/registrations").data["data"]["items"]
    assert row["can_review"] is False
    blocked = client.post(
        "/api/v1/registrations/bulk-approval",
        {
            "action": "approve",
            "comment": "",
            "items": [{"registration_id": draft["id"], "submission_no": 1}],
        },
        format="json",
    )
    assert blocked.data["data"][0]["code"] == 40303


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("action", "status"),
    [("approve", "approved"), ("reject", "rejected"), ("return", "returned")],
)
def test_bulk_review_has_independent_scoped_versioned_results(
    dataset, actor_client, draft_payload, action, status
):
    client, first = create_draft(actor_client, dataset, draft_payload)
    assert submit(client, first, "bulk-team-submission").status_code == 200
    individual = {
        key: value for key, value in draft_payload.items() if key != "team_id"
    }
    individual["enrollment_kind"] = "individual"
    _, second = create_draft(actor_client, dataset, individual)
    assert submit(client, second, "bulk-individual-submission").status_code == 200
    targets = [
        {"registration_id": second["id"], "submission_no": 2},
        {"registration_id": first["id"], "submission_no": 1},
        {"registration_id": second["id"] + 99, "submission_no": 1},
    ]
    endpoint = "/api/v1/registrations/bulk-approval"
    payload = {"action": action, "comment": "Synthetic decision", "items": targets}
    assert client.post(endpoint, payload, format="json").status_code == 403
    outsider = actor_client(dataset["accounts"]["outsider"])
    UserRole.objects.create(
        user=dataset["accounts"]["outsider"],
        role=Role.objects.get(code="reviewer"),
        scope_type="edition",
        scope_id=dataset["edition"].id + 99,
    )
    invisible = outsider.post(endpoint, payload, format="json").data["data"]
    assert [item["code"] for item in invisible] == [40401, 40401, 40401]
    reviewer = actor_client(dataset["accounts"]["reviewer"])
    assert all(
        row["can_review"]
        for row in reviewer.get("/api/v1/registrations").data["data"]["items"]
    )
    assert (
        reviewer.post(
            endpoint, {**payload, "items": [targets[1], targets[1]]}, format="json"
        ).status_code
        == 400
    )
    assert (
        reviewer.post(endpoint, {**payload, "items": []}, format="json").status_code
        == 400
    )
    oversize = [
        {"registration_id": number, "submission_no": 1} for number in range(1, 22)
    ]
    assert (
        reviewer.post(
            endpoint, {**payload, "items": oversize}, format="json"
        ).status_code
        == 400
    )
    assert (
        reviewer.post(
            endpoint, {**payload, "action": "return", "comment": "  "}, format="json"
        ).status_code
        == 400
    )

    response = reviewer.post(endpoint, payload, format="json")
    assert response.status_code == 200, response.data
    assert response.data["data"] == [
        {"registration_id": second["id"], "code": 40906, "status": None},
        {"registration_id": first["id"], "code": 0, "status": status},
        {"registration_id": second["id"] + 99, "code": 40401, "status": None},
    ]
    assert (
        reviewer.post(endpoint, payload, format="json").data["data"][1]["code"] == 40902
    )
    item = Registration.objects.get(pk=first["id"])
    assert item.status == status and item.approval_records.count() == 1
    assert (
        RegistrationNotice.objects.filter(registration=item, kind=status).count() == 1
    )
    assert Registration.objects.get(pk=second["id"]).status == "pending_review"


@pytest.mark.django_db
def test_manager_cannot_read_unsubmitted_draft_and_closed_history_requires_permission(
    dataset, actor_client, draft_payload
):
    student, draft = create_draft(actor_client, dataset, draft_payload)
    reviewer = actor_client(dataset["accounts"]["reviewer"])
    assert reviewer.get(f"/api/v1/registrations/{draft['id']}").status_code == 404
    assert reviewer.get("/api/v1/registrations").data["data"]["total"] == 0
    assert submit(student, draft).status_code == 200
    role = Role.objects.get(code="reviewer")
    role.permissions.remove(*role.permissions.filter(code="registration:read_history"))
    edition = dataset["edition"]
    edition.status = "closed"
    edition.save(update_fields=["status"])
    assert reviewer.get(f"/api/v1/registrations/{draft['id']}").status_code == 404
    assert reviewer.get("/api/v1/registrations").data["data"]["total"] == 0
    assert student.get(f"/api/v1/registrations/{draft['id']}").status_code == 404


@pytest.mark.django_db
def test_returned_draft_changes_do_not_leak_into_current_submission(
    dataset, actor_client, draft_payload
):
    student, draft = create_draft(actor_client, dataset, draft_payload)
    assert submit(student, draft).status_code == 200
    reviewer = actor_client(dataset["accounts"]["reviewer"])
    response = reviewer.post(
        f"/api/v1/registrations/{draft['id']}/approval",
        {"action": "return", "comment": "Needs corrections", "submission_no": 1},
        format="json",
    )
    new_group = Group.objects.create(
        edition=dataset["edition"],
        code="MS",
        name="Middle school",
        school_level="MS",
        enrollment_type="team",
    )
    other_event = Event.objects.create(
        edition=dataset["edition"], code_id="VURC", name="VURC"
    )
    new_offering = Offering.objects.create(
        edition=dataset["edition"], event=other_event, group=new_group
    )
    response = student.patch(
        f"/api/v1/registrations/{draft['id']}",
        {
            "version": response.data["data"]["version"],
            "offering_id": new_offering.id,
            "selected_school_level": "MS",
            "coach_user_id": None,
            "contact": {
                "name": "Private new contact",
                "phone": "00000000001",
                "email": None,
            },
        },
        format="json",
    )
    assert response.status_code == 200, response.data
    current = reviewer.get(f"/api/v1/registrations/{draft['id']}").data["data"]
    assert current["offering_id"] == dataset["offering"].id
    assert current["selected_school_level"] == "HS"
    assert current["coach_user_id"] == dataset["accounts"]["coach"].id
    assert current["contact"]["name"] == "Synthetic contact"
    old_offering = dataset["offering"]
    queue = "/api/v1/registrations"
    filters = {
        "edition": draft["edition_id"],
        "event": old_offering.event_id,
        "group": old_offering.group_id,
        "org": draft["org_id"],
        "status": "returned",
        "q": dataset["team"].team_number.code,
    }
    listed = reviewer.get(queue, filters)
    assert listed.status_code == 200, listed.data
    (row,) = listed.data["data"]["items"]
    assert row["id"] == draft["id"] and row["submission_no"] == 1
    assert (
        row["event_name"] == old_offering.event.name
        and row["group_name"] == old_offering.group.name
    )
    assert not {"contact", "members", "consents", "approval_records"}.intersection(row)
    for field, value in (
        ("event", other_event.id),
        ("group", new_group.id),
        ("q", "DOES-NOT-EXIST"),
    ):
        assert reviewer.get(queue, {**filters, field: value}).data["data"]["total"] == 0
    assert reviewer.get(queue, {"group": "-2"}).status_code == 400
    assert reviewer.get(queue, {"status": "bad"}).status_code == 400
    facets = f"{queue}/filter-options"
    assert reviewer.get(facets, {"dimension": "group"}).data["data"]["items"] == [
        {"id": old_offering.group_id, "name": old_offering.group.name}
    ]
    assert (
        reviewer.get(
            facets, {"dimension": "event", "edition": draft["edition_id"] + 100}
        ).data["data"]["total"]
        == 0
    )
    assert reviewer.get(facets, {"dimension": "unknown"}).status_code == 400
    outsider = actor_client(dataset["accounts"]["outsider"])
    assert outsider.get(facets, {"dimension": "group"}).data["data"]["total"] == 0
    assert outsider.get(queue, filters).data["data"]["total"] == 0

    revised_offering = Offering.objects.create(
        edition=dataset["edition"], event=old_offering.event, group=new_group
    )
    patched = student.patch(
        f"/api/v1/registrations/{draft['id']}",
        {
            "version": response.data["data"]["version"],
            "offering_id": revised_offering.id,
            "coach_user_id": dataset["accounts"]["coach"].id,
        },
        format="json",
    )
    assert patched.status_code == 200, patched.data
    resubmitted = student.post(
        f"/api/v1/registrations/{draft['id']}/resubmit",
        {"version": patched.data["data"]["version"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="review-queue-resubmit",
    )
    assert resubmitted.status_code == 200, resubmitted.data
    assert (
        reviewer.get(queue, {"group": old_offering.group_id}).data["data"]["total"] == 0
    )
    (row,) = reviewer.get(queue, {"group": new_group.id}).data["data"]["items"]
    assert row["group_name"] == new_group.name and row["submission_no"] == 2
    history = f"{queue}/{draft['id']}/submissions"
    first, second = reviewer.get(history).data["data"]["items"]
    assert (
        first["offering_id"] == old_offering.id
        and first["group_name"] == old_offering.group.name
    )
    assert (
        second["offering_id"] == revised_offering.id
        and second["group_name"] == new_group.name
    )
    assert student.get(f"{history}/1").data["data"] == first
    assert reviewer.get(history, {"page_size": 1, "page": 2}).data["data"]["items"] == [
        second
    ]
    assert reviewer.get(f"{history}/3").status_code == 404
    assert outsider.get(f"{history}/1").status_code == 404
    assert outsider.get(history).status_code == 404
    assert set(first["members"][0]) == {
        "user_id",
        "real_name",
        "role",
        "school_level",
        "grade",
    }


@pytest.mark.django_db
def test_cancel_preserves_round_and_rejects_stale_review(
    dataset, actor_client, draft_payload
):
    student, draft = create_draft(actor_client, dataset, draft_payload)
    submitted = submit(student, draft).data["data"]
    canceled = student.post(
        f"/api/v1/registrations/{draft['id']}/cancel-review",
        {"version": submitted["version"]},
        format="json",
    )
    assert canceled.status_code == 200, canceled.data
    assert canceled.data["data"]["status"] == "draft"
    path = f"/api/v1/registrations/{draft['id']}/submissions/1"
    cancelled_round = student.get(path).data["data"]
    assert (
        cancelled_round["cancelled_at"] is not None
        and cancelled_round["offering_id"] == dataset["offering"].id
    )
    assert (
        RegistrationSubmission.objects.get(registration_id=draft["id"]).cancelled_at
        is not None
    )
    stale = actor_client(dataset["accounts"]["reviewer"]).post(
        f"/api/v1/registrations/{draft['id']}/approval",
        {"action": "approve", "comment": "", "submission_no": 1},
        format="json",
    )
    assert stale.status_code == 409


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["reject", "return"])
def test_review_requires_nonblank_rejection_or_return_reason(
    dataset, actor_client, draft_payload, action
):
    student, draft = create_draft(actor_client, dataset, draft_payload)
    submitted = submit(student, draft).data["data"]
    reviewer = actor_client(dataset["accounts"]["reviewer"])
    url = f"/api/v1/registrations/{draft['id']}"
    response = reviewer.post(
        f"{url}/approval",
        {"action": action, "comment": "   ", "submission_no": 1},
        format="json",
    )
    assert response.status_code == 400 and "comment" in response.data["errors"]
    still_pending = reviewer.get(url).data["data"]
    assert still_pending["version"] == submitted["version"]
    assert (
        still_pending["status"] == "pending_review"
        and not still_pending["approval_records"]
    )


@pytest.mark.django_db
def test_weak_password_is_safe_validation_error(dataset, actor_client):
    response = actor_client(dataset["accounts"]["student"]).post(
        "/api/v1/auth/password/change",
        {"old_password": "Synthetic-flow-test-2026!", "new_password": "111111111111"},
        format="json",
    )
    assert response.status_code == 400 and response.data["code"] == 40001
    assert "Synthetic-flow" not in str(response.data)


@pytest.mark.django_db
def test_stale_token_version_is_denied(dataset, actor_client):
    client = actor_client(dataset["accounts"]["student"])
    user = dataset["accounts"]["student"]
    user.token_version += 1
    user.save(update_fields=["token_version"])
    assert client.get("/api/v1/me").status_code == 401


@pytest.mark.django_db
def test_public_payload_does_not_expose_drafts(dataset):
    client = APIClient()
    assert client.get("/api/v1/public/competitions").data["data"]["total"] == 1
    assert client.get("/api/v1/public/competitions?season=all").status_code == 400
    item = dataset["edition"]
    item.status = "draft"
    item.save(update_fields=["status"])
    assert client.get(f"/api/v1/public/editions/{item.id}").status_code == 404
    assert client.get("/api/v1/public/competitions").data["data"]["total"] == 0

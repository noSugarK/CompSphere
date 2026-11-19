import copy
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.events.models import Offering
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
    new_offering = Offering.objects.create(
        edition=dataset["edition"], event=dataset["offering"].event, group=new_group
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

import pytest
from rest_framework.test import APIClient

from apps.rbac.models import UserRole
from apps.teams.models import SeasonRegistration, Team


def proposal(dataset):
    return {
        "request_kind": "create",
        "org_id": dataset["school"].id,
        "team_code": "DEVNEW",
        "event_code": "V5RC",
        "registration_season_id": dataset["season"].id,
        "proposal": {
            "name": "A new synthetic team",
            "coach_id": dataset["accounts"]["coach"].id,
            "captain_id": None,
            "members": [],
        },
    }


@pytest.mark.django_db
def test_team_creation_only_becomes_official_after_nonself_review(
    dataset, actor_client
):
    manager = actor_client(dataset["accounts"]["manager"])
    result = manager.post(
        "/api/v1/team-change-requests", proposal(dataset), format="json"
    )
    assert result.status_code == 201, result.data
    request_id = result.data["data"]["id"]
    assert not Team.objects.filter(team_number__code="DEVNEW").exists()
    assert (
        manager.post(
            f"/api/v1/team-change-requests/{request_id}/submit", {}, format="json"
        ).status_code
        == 200
    )
    assert (
        manager.post(
            f"/api/v1/team-change-requests/{request_id}/review",
            {"action": "approve", "comment": ""},
            format="json",
        ).status_code
        == 403
    )
    result = actor_client(dataset["accounts"]["platform"]).post(
        f"/api/v1/team-change-requests/{request_id}/review",
        {"action": "approve", "comment": ""},
        format="json",
    )
    assert result.status_code == 200, result.data
    team = Team.objects.get(team_number__code="DEVNEW")
    assert team.approved_revision_id == request_id
    assert SeasonRegistration.objects.filter(
        team=team, season=dataset["season"], status="approved"
    ).exists()


@pytest.mark.django_db
def test_platform_cannot_approve_own_team_request(dataset, actor_client):
    platform = actor_client(dataset["accounts"]["platform"])
    result = platform.post(
        "/api/v1/team-change-requests", proposal(dataset), format="json"
    )
    assert result.status_code == 201, result.data
    pk = result.data["data"]["id"]
    assert (
        platform.post(
            f"/api/v1/team-change-requests/{pk}/submit", {}, format="json"
        ).status_code
        == 200
    )
    response = platform.post(
        f"/api/v1/team-change-requests/{pk}/review",
        {"action": "approve", "comment": ""},
        format="json",
    )
    assert response.status_code == 403 and response.data["code"] == 40303


@pytest.mark.django_db
def test_coach_cannot_write_team_and_manager_cannot_cross_org(dataset, actor_client):
    response = actor_client(dataset["accounts"]["coach"]).post(
        "/api/v1/team-change-requests", proposal(dataset), format="json"
    )
    assert response.status_code == 403
    payload = proposal(dataset)
    payload["org_id"] = dataset["other_school"].id
    response = actor_client(dataset["accounts"]["manager"]).post(
        "/api/v1/team-change-requests", payload, format="json"
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_unknown_nested_team_fields_cannot_set_status(dataset, actor_client):
    payload = proposal(dataset)
    payload["proposal"]["status"] = "approved"
    response = actor_client(dataset["accounts"]["manager"]).post(
        "/api/v1/team-change-requests", payload, format="json"
    )
    assert response.status_code == 400 and response.data["code"] == 40001


@pytest.mark.django_db
def test_current_membership_cannot_be_bypassed(dataset, actor_client):
    payload = proposal(dataset)
    payload["proposal"]["captain_id"] = dataset["accounts"]["student"].id
    payload["proposal"]["members"] = [
        {"user_id": dataset["accounts"]["student"].id, "role": "captain"}
    ]
    response = actor_client(dataset["accounts"]["manager"]).post(
        "/api/v1/team-change-requests", payload, format="json"
    )
    assert response.status_code == 409 and response.data["code"] == 40908


@pytest.mark.django_db
def test_refresh_requires_csrf_and_origin_and_rotates_cookie(dataset):
    client = APIClient(enforce_csrf_checks=True)
    response = client.post(
        "/api/v1/auth/login",
        {
            "login_type": "email",
            "email": "student@dev.example",
            "password": "Synthetic-flow-test-2026!",
        },
        format="json",
    )
    access = response.data["data"]["access"]
    old_refresh = client.cookies["refresh"].value
    assert (
        client.post(
            "/api/v1/auth/refresh", {}, format="json", HTTP_ORIGIN="http://testserver"
        ).status_code
        == 403
    )
    token = client.get("/api/v1/auth/csrf").data["data"]["csrf_token"]
    assert (
        client.post(
            "/api/v1/auth/refresh",
            {},
            format="json",
            HTTP_ORIGIN="http://evil.example",
            HTTP_X_CSRFTOKEN=token,
        ).status_code
        == 403
    )
    refreshed = client.post(
        "/api/v1/auth/refresh",
        {},
        format="json",
        HTTP_ORIGIN="http://testserver",
        HTTP_X_CSRFTOKEN=token,
    )
    assert refreshed.status_code == 200, refreshed.data
    assert client.cookies["refresh"].value != old_refresh
    new_refresh = client.cookies["refresh"].value
    client.cookies["refresh"] = old_refresh
    assert (
        client.post(
            "/api/v1/auth/refresh",
            {},
            format="json",
            HTTP_ORIGIN="http://testserver",
            HTTP_X_CSRFTOKEN=token,
        ).status_code
        == 401
    )
    client.cookies["refresh"] = new_refresh
    client.credentials(HTTP_AUTHORIZATION="Bearer " + access)
    assert (
        client.post(
            "/api/v1/auth/logout",
            {},
            format="json",
            HTTP_ORIGIN="http://testserver",
            HTTP_X_CSRFTOKEN=token,
        ).status_code
        == 200
    )
    assert client.get("/api/v1/me").status_code == 401


@pytest.mark.django_db
def test_required_password_change_restricts_business_routes(dataset, actor_client):
    user = dataset["accounts"]["student"]
    user.must_change_password = True
    user.save(update_fields=["must_change_password"])
    client = actor_client(user)
    assert client.get("/api/v1/me").status_code == 200
    assert client.get("/api/v1/teams").status_code == 403


@pytest.mark.django_db
def test_team_read_revocation_is_live(dataset, actor_client):
    client = actor_client(dataset["accounts"]["manager"])
    assert client.get("/api/v1/teams").data["data"]["total"] == 1
    UserRole.objects.filter(user=dataset["accounts"]["manager"]).delete()
    assert client.get("/api/v1/teams").data["data"]["total"] == 0

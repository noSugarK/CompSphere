import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_dashboard_counts_scoped_by_role(dataset, actor_client, approved_registration):
    platform = actor_client(dataset["accounts"]["platform"])
    body = platform.get("/api/v1/stats/dashboard").data["data"]
    assert body["registrations"] >= 1 and body["approved"] >= 1
    assert body["awarded"] == 0
    assert 0 < body["approval_rate"] <= 1
    assert {"users", "organizations", "competitions", "editions"} <= set(body)

    # 赛事作用域读者：无平台盘子字段，计数只覆盖其届次。
    organizer = actor_client(dataset["accounts"]["organizer"])
    scoped = organizer.get("/api/v1/stats/dashboard").data["data"]
    assert "users" not in scoped and "editions" not in scoped
    assert scoped["registrations"] == body["registrations"]

    # 无任何 stats 权限的账号被拒。
    student = actor_client(dataset["accounts"]["student"])
    assert student.get("/api/v1/stats/dashboard").data["code"] == 40301
    assert APIClient().get("/api/v1/stats/dashboard").status_code == 401


@pytest.mark.django_db
def test_dashboard_excludes_unsubmitted_and_counts_awarded(
    dataset, actor_client, draft_payload, approved_registration
):
    edition = dataset["edition"]
    student = actor_client(dataset["accounts"]["student"])
    organizer = actor_client(dataset["accounts"]["organizer"])
    before = organizer.get("/api/v1/stats/dashboard").data["data"]
    assert before["registrations"] == 1
    # 草稿不进入看板分母。
    student.post(
        f"/api/v1/editions/{edition.id}/registrations",
        {**draft_payload, "submit": False},
        format="json",
    )
    after = organizer.get("/api/v1/stats/dashboard").data["data"]
    assert after["registrations"] == 1

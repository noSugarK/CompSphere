import pytest

from apps.audit.models import AuditLog
from apps.audit.services import audit


@pytest.mark.django_db
def test_audit_logs_are_scoped_per_reader(dataset, actor_client):
    edition = dataset["edition"]
    team = dataset["team"]
    organizer = actor_client(dataset["accounts"]["organizer"])
    manager = actor_client(dataset["accounts"]["manager"])
    platform = actor_client(dataset["accounts"]["platform"])
    student = actor_client(dataset["accounts"]["student"])

    # 产生三类可见性不同的事件。
    audit(
        dataset["accounts"]["organizer"],
        "roster.confirmed",
        "award_roster",
        901,
        scope={"edition_id": edition.id},
    )
    audit(
        dataset["accounts"]["manager"],
        "team.request.approved",
        "team_request",
        902,
        scope={"org_id": team.org_id},
    )
    scoped_edition = AuditLog.objects.get(resource="award_roster")
    scoped_org = AuditLog.objects.get(resource="team_request")

    rows = organizer.get("/api/v1/audit-logs").data["data"]
    assert [item["id"] for item in rows["items"]] == [scoped_edition.id]
    # 单位管理员看不到赛事级事件，反之亦然。
    assert [
        item["id"] for item in manager.get("/api/v1/audit-logs").data["data"]["items"]
    ] == [scoped_org.id]
    all_rows = platform.get("/api/v1/audit-logs?page_size=100").data["data"]
    assert scoped_edition.id in [i["id"] for i in all_rows["items"]]
    assert scoped_org.id in [i["id"] for i in all_rows["items"]]
    # 无 audit:read 的账号被拒。
    assert student.get("/api/v1/audit-logs").data["code"] == 40301


@pytest.mark.django_db
def test_audit_filters_by_actor_resource_and_date(dataset, actor_client):
    edition = dataset["edition"]
    organizer = actor_client(dataset["accounts"]["organizer"])
    audit(
        dataset["accounts"]["organizer"],
        "roster.confirmed",
        "award_roster",
        911,
        scope={"edition_id": edition.id},
    )
    audit(
        dataset["accounts"]["platform"],
        "edition.published",
        "edition",
        912,
        scope={"edition_id": edition.id},
    )
    url = "/api/v1/audit-logs"
    by_resource = organizer.get(url, {"resource": "award_roster"}).data["data"]
    assert [i["resource"] for i in by_resource["items"]] == ["award_roster"]
    by_actor = organizer.get(
        url, {"actor": dataset["accounts"]["platform"].id}
    ).data["data"]
    assert [i["resource"] for i in by_actor["items"]] == ["edition"]
    assert organizer.get(url, {"actor": 999999}).data["data"]["total"] == 0
    future = organizer.get(url, {"date_from": "2099-01-01"}).data["data"]
    assert future["total"] == 0
    assert organizer.get(url, {"date_from": "not-a-date"}).data["code"] == 40001

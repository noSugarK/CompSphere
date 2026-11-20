import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.orgs.models import OrganizationMember
from apps.profiles.models import IdentityChangeRequest

# 仅用于本地测试的合成证件号（非真实身份），末位按身份证校验位规则计算。
ID_A = "110101200001010010"
ID_B = "310101200102020020"
ID_TAKEN = "440101200203030032"
PASSWORD = "Synthetic-flow-test-2026!"


def provision(client, org_id, number, key=None, name="Synthetic student", **body):
    return client.post(
        f"/api/v1/orgs/{org_id}/student-accounts",
        {
            "real_name": name,
            "document_type": "id_card",
            "document_country": "CN",
            "document_number": number,
            **body,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=key or f"provision-{number}",
    )


def create_request(client, user_id, document_type, country, number):
    return client.post(
        "/api/v1/identity-change-requests",
        {
            "user_id": user_id,
            "document_type": document_type,
            "document_country": country,
            "document_number": number,
        },
        format="json",
    )


@pytest.mark.django_db
def test_provision_creates_document_bound_first_login_account(dataset, actor_client):
    manager = actor_client(dataset["accounts"]["manager"])
    response = provision(manager, dataset["school"].id, ID_A)
    assert response.status_code == 201, response.data
    body = response.data["data"]
    assert body["must_change_password"] is True
    assert body["document_last4"] == ID_A[-4:]
    assert ID_A not in response.content.decode()
    password = body["temporary_password"]
    user = User.objects.get(pk=body["id"])
    assert user.profile.document_hash and user.profile.identity_version == 1
    assert user.account_source == "org"
    assert user.created_by_org_id == dataset["school"].id
    assert OrganizationMember.objects.filter(
        user=user, is_primary=True, org_id=dataset["school"].id
    ).exists()
    # 代建账户以「证件类型+签发国+号码+密码」登录。
    anonymous = APIClient()
    logged_in = anonymous.post(
        "/api/v1/auth/login",
        {
            "login_type": "document",
            "document_type": "id_card",
            "document_country": "CN",
            "document_number": ID_A,
            "password": password,
        },
        format="json",
    )
    assert logged_in.status_code == 200, logged_in.data
    assert logged_in.data["data"]["access"]
    # 已绑定证件不得静默接管账号。
    again = provision(manager, dataset["school"].id, ID_A, key="dup-key-1")
    assert again.data["code"] == 40904


@pytest.mark.django_db
def test_provision_retry_never_redelivers_password(dataset, actor_client):
    manager = actor_client(dataset["accounts"]["manager"])
    first = provision(manager, dataset["school"].id, ID_A, key="idempotency-key-1")
    assert first.status_code == 201
    assert first.data["data"]["temporary_password"]
    retry = provision(manager, dataset["school"].id, ID_A, key="idempotency-key-1")
    # 06 §76：重试创建请求不能返回原密码，只回放账号事实。
    assert retry.status_code == 201, retry.data
    assert "temporary_password" not in retry.data["data"]
    assert retry.data["data"]["id"] == first.data["data"]["id"]


@pytest.mark.django_db
def test_failed_provision_does_not_poison_idempotency_key(dataset, actor_client):
    manager = actor_client(dataset["accounts"]["manager"])
    failed = provision(
        manager, dataset["school"].id, "110101200101010019", key="same-key-1"
    )
    assert failed.data["code"] == 42206  # 校验位错误，账号未创建
    assert not User.objects.filter(profile__document_last4="0019").exists()
    ok = provision(manager, dataset["school"].id, ID_A, key="same-key-1")
    assert ok.status_code == 201, ok.data


@pytest.mark.django_db
def test_provision_validates_document_and_scope(dataset, actor_client):
    manager = actor_client(dataset["accounts"]["manager"])
    bad = provision(
        manager, dataset["school"].id, "110101200001010011", key="bad-doc-key"
    )
    assert bad.data["code"] == 42206  # 身份证校验位错误
    short_passport = manager.post(
        f"/api/v1/orgs/{dataset['school'].id}/student-accounts",
        {
            "real_name": "Synthetic",
            "document_type": "passport",
            "document_country": "US",
            "document_number": "AB",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="short-passport-key",
    )
    assert short_passport.data["code"] == 42206
    foreign = provision(
        manager, dataset["other_school"].id, ID_A, key="foreign-org-key"
    )
    assert foreign.data["code"] in (40301, 40401)
    student = actor_client(dataset["accounts"]["student"])
    denied = provision(student, dataset["school"].id, ID_B, key="denied-role-key")
    assert denied.data["code"] == 40301
    assert not User.objects.filter(profile__document_last4=ID_B[-4:]).exists()


@pytest.mark.django_db
def test_identity_change_approve_switches_binding_and_revokes_session(
    dataset, actor_client
):
    manager = actor_client(dataset["accounts"]["manager"])
    created = provision(manager, dataset["school"].id, ID_A).data["data"]
    student = User.objects.get(pk=created["id"])
    item = create_request(manager, student.id, "id_card", "CN", ID_B).data["data"]
    assert item["status"] == "draft" and item["base_identity_version"] == 1
    assert item["new_document_last4"] == ID_B[-4:] and item["has_old_document"]
    submitted = manager.post(
        f"/api/v1/identity-change-requests/{item['id']}/submit", {}, format="json"
    ).data["data"]
    assert submitted["status"] == "submitted"
    # 申请人不得自审（02 §证件与代建）。
    self_review = manager.post(
        f"/api/v1/identity-change-requests/{item['id']}/review",
        {"action": "approve", "comment": "", "version": 1},
        format="json",
    )
    assert self_review.data["code"] == 40303
    platform = actor_client(dataset["accounts"]["platform"])
    token_before = student.token_version
    approved = platform.post(
        f"/api/v1/identity-change-requests/{item['id']}/review",
        {"action": "approve", "comment": "", "version": 1},
        format="json",
    )
    assert approved.status_code == 200, approved.data
    student.refresh_from_db()
    profile = student.profile
    assert profile.document_last4 == ID_B[-4:]
    assert profile.identity_version == 2
    assert profile.identity_change_request_id == item["id"]
    assert ID_B not in str(approved.data)
    assert student.token_version == token_before + 1  # 旧会话失效
    # 批准释放旧号：同证件可再代建。
    assert (
        provision(
            manager, dataset["school"].id, ID_A, key="release-old-key"
        ).status_code
        == 201
    )


@pytest.mark.django_db
def test_identity_change_conflict_and_single_pending(dataset, actor_client):
    manager = actor_client(dataset["accounts"]["manager"])
    created = provision(manager, dataset["school"].id, ID_A).data["data"]
    provision(manager, dataset["school"].id, ID_TAKEN, key="taken-doc-key")
    platform = actor_client(dataset["accounts"]["platform"])
    item = create_request(manager, created["id"], "id_card", "CN", ID_TAKEN).data[
        "data"
    ]
    manager.post(
        f"/api/v1/identity-change-requests/{item['id']}/submit", {}, format="json"
    )
    review = platform.post(
        f"/api/v1/identity-change-requests/{item['id']}/review",
        {"action": "approve", "comment": "", "version": 1},
        format="json",
    )
    assert review.data["code"] == 40904
    # 同一时间仅一条待处理申请。
    second = create_request(manager, created["id"], "passport", "US", "E12345678")
    assert second.data["code"] == 40901


@pytest.mark.django_db
def test_identity_change_review_rules(dataset, actor_client):
    manager = actor_client(dataset["accounts"]["manager"])
    created = provision(manager, dataset["school"].id, ID_A).data["data"]
    item = create_request(manager, created["id"], "id_card", "CN", ID_B).data["data"]
    # 草稿可改，提交后不可改。
    edited = manager.patch(
        f"/api/v1/identity-change-requests/{item['id']}",
        {
            "document_type": "passport",
            "document_country": "US",
            "document_number": "E7654321",
        },
        format="json",
    ).data["data"]
    assert edited["new_document_type"] == "passport"
    manager.post(
        f"/api/v1/identity-change-requests/{item['id']}/submit", {}, format="json"
    )
    assert (
        manager.patch(
            f"/api/v1/identity-change-requests/{item['id']}",
            {
                "document_type": "id_card",
                "document_country": "CN",
                "document_number": ID_B,
            },
            format="json",
        ).data["code"]
        == 40902
    )
    platform = actor_client(dataset["accounts"]["platform"])
    assert (
        platform.post(
            f"/api/v1/identity-change-requests/{item['id']}/review",
            {"action": "return", "comment": "  ", "version": 1},
            format="json",
        ).data["code"]
        == 40001
    )
    assert (
        platform.post(
            f"/api/v1/identity-change-requests/{item['id']}/review",
            {"action": "approve", "comment": "", "version": 99},
            format="json",
        ).data["code"]
        == 40906
    )
    returned = platform.post(
        f"/api/v1/identity-change-requests/{item['id']}/review",
        {"action": "return", "comment": "Re-submit a clearer copy", "version": 1},
        format="json",
    ).data["data"]
    assert returned["status"] == "returned"
    assert returned["comment"] == "Re-submit a clearer copy"
    # 已审申请不能走取消留档。
    assert (
        manager.post(
            f"/api/v1/identity-change-requests/{item['id']}/cancel-and-edit",
            {},
            format="json",
        ).data["code"]
        == 40902
    )


@pytest.mark.django_db
def test_cancel_keeps_record_and_copies_draft(dataset, actor_client):
    manager = actor_client(dataset["accounts"]["manager"])
    created = provision(manager, dataset["school"].id, ID_A).data["data"]
    item = create_request(manager, created["id"], "id_card", "CN", ID_B).data["data"]
    manager.post(
        f"/api/v1/identity-change-requests/{item['id']}/submit", {}, format="json"
    )
    replacement = manager.post(
        f"/api/v1/identity-change-requests/{item['id']}/cancel-and-edit?copy_draft=true",
        {},
        format="json",
    ).data["data"]
    assert replacement["status"] == "draft"
    assert replacement["id"] != item["id"]
    original = IdentityChangeRequest.objects.get(pk=item["id"])
    assert original.status == "withdrawn"
    assert original.resubmission_of_id is None
    assert replacement["new_document_last4"] == ID_B[-4:]
    # 留档后仍只有一条待处理申请。
    assert (
        IdentityChangeRequest.objects.filter(
            user_id=created["id"], status__in=("draft", "submitted")
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_reset_student_password_scoped_and_race_guarded(dataset, actor_client):
    manager = actor_client(dataset["accounts"]["manager"])
    created = provision(manager, dataset["school"].id, ID_A).data["data"]
    membership = OrganizationMember.objects.get(user_id=created["id"], is_primary=True)
    url = f"/api/v1/users/{created['id']}/reset-student-password"
    assert (
        manager.post(
            url,
            {
                "primary_membership_id": membership.id,
                "affiliation_version": 7,
                "reason": "Verified in person",
            },
            format="json",
        ).data["code"]
        == 40906
    )
    assert (
        manager.post(
            url,
            {
                "primary_membership_id": membership.id,
                "affiliation_version": 0,
                "reason": "   ",
            },
            format="json",
        ).data["code"]
        == 40001
    )
    ok = manager.post(
        url,
        {
            "primary_membership_id": membership.id,
            "affiliation_version": 0,
            "reason": "Verified in person",
        },
        format="json",
    )
    assert ok.status_code == 200, ok.data
    assert ok.headers["Cache-Control"] == "no-store"
    assert ok.data["data"]["temporary_password"]
    user = User.objects.get(pk=created["id"])
    assert user.must_change_password and user.token_version == 1
    # 其他单位无权重置。
    outsider = actor_client(dataset["accounts"]["outsider"])
    assert outsider.post(
        url,
        {
            "primary_membership_id": membership.id,
            "affiliation_version": 0,
            "reason": "attempts",
        },
        format="json",
    ).data["code"] in (40301, 40401)


@pytest.mark.django_db
def test_org_admin_cannot_reset_non_student_account(dataset, actor_client):
    # 02 §证件与代建：单位重置限普通学生；教练账号由平台处理。
    manager = actor_client(dataset["accounts"]["manager"])
    coach = dataset["accounts"]["coach"]
    membership = OrganizationMember.objects.get(user=coach, is_primary=True)
    response = manager.post(
        f"/api/v1/users/{coach.id}/reset-student-password",
        {
            "primary_membership_id": membership.id,
            "affiliation_version": coach.affiliation_version,
            "reason": "claims to be the coach",
        },
        format="json",
    )
    assert response.data["code"] == 40301
    coach.refresh_from_db()
    assert not coach.must_change_password
    # 平台管理员可处理。
    platform = actor_client(dataset["accounts"]["platform"])
    reset = platform.post(
        f"/api/v1/users/{coach.id}/reset-student-password",
        {
            "primary_membership_id": membership.id,
            "affiliation_version": coach.affiliation_version,
            "reason": "Identity verified against documents",
        },
        format="json",
    )
    assert reset.status_code == 200, reset.data


@pytest.mark.django_db
def test_requests_visible_only_to_participants_and_reviewers(dataset, actor_client):
    manager = actor_client(dataset["accounts"]["manager"])
    created = provision(manager, dataset["school"].id, ID_A).data["data"]
    item = create_request(manager, created["id"], "id_card", "CN", ID_B).data["data"]
    outsider = actor_client(dataset["accounts"]["outsider"])
    assert (
        outsider.get(f"/api/v1/identity-change-requests/{item['id']}").status_code
        == 404
    )
    assert [
        row["id"]
        for row in manager.get("/api/v1/identity-change-requests").data["data"]
    ] == [item["id"]]
    assert outsider.get("/api/v1/identity-change-requests").data["data"] == []


@pytest.mark.django_db
def test_profile_document_fields_never_leave_the_server(dataset, actor_client):
    manager = actor_client(dataset["accounts"]["manager"])
    created = provision(manager, dataset["school"].id, ID_A).data["data"]
    assert ID_A not in str(created)
    assert "document_number" not in str(created) and "document_hash" not in str(created)
    from apps.profiles.models import Profile

    profile = Profile.objects.get(user_id=created["id"])
    assert profile.document_hash and len(profile.document_hash) == 64

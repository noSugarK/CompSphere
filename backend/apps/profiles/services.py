import secrets
from base64 import urlsafe_b64encode
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.services import audit
from apps.orgs.models import Organization, OrganizationMember
from apps.profiles.models import IdentityChangeRequest, Profile
from apps.rbac.services import has_perm, require_perm
from core.crypto import encrypt
from core.documents import bind
from core.exceptions import BusinessError

ADMIN_ROLES = ("platform_admin", "competition_admin", "org_admin")
# 06 §代建与证件更正: 临时密码仅请求体一次性交付，服务器只存哈希。
INITIAL_PASSWORD_TTL = timedelta(days=7)


def create_participant_profile(user, real_name):
    """Registration never sets identity documents or administrative person types."""
    return Profile.objects.create(
        user=user, real_name=real_name, person_type="participant"
    )


def _primary_membership(user):
    return OrganizationMember.objects.filter(
        user=user, is_primary=True, left_at__isnull=True
    ).select_related("org")


def _is_admin(user):
    # 02：管理账号（含 reviewer/教练之外角色）不得由单位重置，交由平台处理。
    from apps.rbac.models import UserRole

    return UserRole.objects.filter(user=user, role__code__in=ADMIN_ROLES).exists()


def _lock_profile(user_id):
    profile = Profile.objects.select_for_update().filter(user_id=user_id).first()
    if profile is None:
        raise BusinessError(40401, "Not found", 404)
    return profile


@transaction.atomic
def provision_student(actor, org_id, data):
    """06 POST /orgs/{id}/student-accounts: 单位代建无邮箱学生账户。
    已存在证件不接管账号；服务器生成 username 与一次性临时密码。"""
    require_perm(actor, "user:provision", org_id=org_id)
    org = Organization.objects.filter(
        pk=org_id, is_deleted=False, status="active"
    ).first()
    if org is None:
        raise BusinessError(40401, "Not found", 404)
    doc_type, country, number, document_hash, last4 = bind(
        data["document_type"], data["document_country"], data["document_number"]
    )
    if Profile.objects.filter(document_hash=document_hash, is_deleted=False).exists():
        raise BusinessError(40904, "This document is already bound to an account")
    password = urlsafe_b64encode(secrets.token_bytes(24)).decode().rstrip("=")
    user = User.objects.create_user(
        email=None,
        password=password,
        status="active",
        phone=(data.get("phone") or "").strip() or None,
        account_source="org",
        created_by=actor,
        created_by_org=org,
        must_change_password=True,
        initial_password_expires_at=timezone.now() + INITIAL_PASSWORD_TTL,
    )
    Profile.objects.create(
        user=user,
        real_name=data["real_name"].strip(),
        person_type="participant",
        document_type=doc_type,
        document_country=country,
        document_number_enc=encrypt(number),
        document_hash=document_hash,
        document_last4=last4,
        identity_version=1,
        student_no=(data.get("student_no") or "").strip() or None,
    )
    OrganizationMember.objects.create(
        org=org, user=user, member_type="student", is_primary=True
    )
    audit(
        actor,
        "account.provision",
        "user",
        user.id,
        scope={"org_id": org.id},
        detail={"document_last4": last4, "document_type": doc_type},
    )
    # 响应含一次性密码：视图层已 no-store，此处只返回一次。
    return user, password


@transaction.atomic
def reset_student_password(actor, user_id, data):
    """06 POST /users/{id}/reset-student-password: 当前有效主属单位核验重置。
    竞态防护：membership_id 与 affiliation_version 必须与库内一致。"""
    target = (
        User.objects.select_for_update().filter(pk=user_id, is_deleted=False).first()
    )
    if target is None:
        raise BusinessError(40401, "Not found", 404)
    membership = (
        OrganizationMember.objects.filter(
            pk=data["primary_membership_id"],
            user=target,
            is_primary=True,
            left_at__isnull=True,
        )
        .select_related("org")
        .first()
    )
    if membership is None:
        raise BusinessError(40401, "Not found", 404)
    require_perm(actor, "user:reset_student_password", org_id=membership.org_id)
    if not (data.get("reason") or "").strip():
        raise BusinessError(40001, "A verification reason is required", 400)
    if target.affiliation_version != data["affiliation_version"]:
        raise BusinessError(40906, "Affiliation has changed, reload the account")
    if _is_admin(target) or membership.member_type != "student":
        # 02：单位重置限本单位普通学生；管理/教练等账号交平台。
        if not has_perm(actor, "user:disable"):
            raise BusinessError(40301, "Only the platform may reset this account", 403)
    password = urlsafe_b64encode(secrets.token_bytes(24)).decode().rstrip("=")
    target.set_password(password)
    target.must_change_password = True
    target.initial_password_expires_at = timezone.now() + INITIAL_PASSWORD_TTL
    target.token_version += 1  # 撤销旧会话
    target.save(
        update_fields=[
            "password",
            "must_change_password",
            "initial_password_expires_at",
            "token_version",
            "updated_at",
        ]
    )
    audit(
        actor,
        "account.reset",
        "user",
        target.id,
        scope={"org_id": membership.org_id},
        detail={
            "reason": data["reason"].strip()[:500],
            "affiliation_version": target.affiliation_version,
        },
    )
    return target, password


def _request_data(item):
    return {
        "id": item.id,
        "user_id": item.user_id,
        "status": item.status,
        "base_identity_version": item.base_identity_version,
        "new_document_type": item.new_document_type,
        "new_document_country": item.new_document_country,
        "new_document_last4": item.new_document_last4,
        "has_old_document": item.old_document_hash is not None,
        "submitted_by": item.submitted_by_id,
        "reviewer_id": item.reviewer_id,
        "comment": item.comment or "",
        "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
        "created_at": item.created_at.isoformat(),
    }


def _reviewer_scope(actor, target):
    """所属单位管理员仅审本单位树内普通成员；平台可审（02 §证件与代建）。"""
    membership = _primary_membership(target).first()
    org_id = membership.org_id if membership else None
    org_ok = org_id is not None and has_perm(
        actor, "profile:review_identity_change", org_id=org_id
    )
    global_ok = has_perm(actor, "profile:review_identity_change")
    if not (org_ok or global_ok):
        raise BusinessError(40301, "Permission denied", 403)
    if org_ok and not global_ok:
        # 单位仅限本范围普通成员，管理/教练账号交平台。
        person = (
            Profile.objects.filter(user=target)
            .values_list("person_type", flat=True)
            .first()
        )
        if person != "participant":
            raise BusinessError(40301, "Only the platform may review this account", 403)


@transaction.atomic
def create_change_request(actor, user_id, data):
    """本人或单位代提；冻结 base 版本与旧绑定，密文只存草稿行。"""
    target = User.objects.filter(pk=user_id, is_deleted=False).first()
    if target is None:
        raise BusinessError(40401, "Not found", 404)
    if target.id == actor.id:
        # 本人申请：受对象归属约束的 personal grant（02 §特殊规则1）。
        require_perm(actor, "profile:request_identity_change", own=True)
    else:
        # 单位代提：仅本单位范围内的普通成员（02 §证件与代建）。
        membership = _primary_membership(target).first()
        if membership is None or not has_perm(
            actor,
            "profile:request_identity_change",
            org_id=membership.org_id,
        ):
            raise BusinessError(40301, "Permission denied", 403)
    profile = _lock_profile(target.id)
    if (
        IdentityChangeRequest.objects.filter(
            user=target, status__in=("draft", "submitted")
        )
        .select_for_update()
        .exists()
    ):
        raise BusinessError(40901, "An identity change is already pending")
    doc_type, country, number, document_hash, last4 = bind(
        data["document_type"], data["document_country"], data["document_number"]
    )
    item = IdentityChangeRequest.objects.create(
        user=target,
        base_identity_version=profile.identity_version,
        old_document_hash=profile.document_hash,
        new_document_type=doc_type,
        new_document_country=country,
        new_document_number_enc=encrypt(number),
        new_document_hash=document_hash,
        new_document_last4=last4,
        status="draft",
        submitted_by=actor,
    )
    audit(
        actor,
        "identity.change.created",
        "identity_change_request",
        item.id,
        scope={"target_user_id": target.id},
        detail={"base_identity_version": item.base_identity_version},
    )
    return _request_data(item)


def visible_request(actor, item):
    if item.submitted_by_id == actor.id or item.user_id == actor.id:
        return True
    membership = _primary_membership(item.user).first()
    org_id = membership.org_id if membership else None
    return has_perm(actor, "profile:review_identity_change", org_id=org_id) or has_perm(
        actor, "profile:review_identity_change"
    )


def get_change_request(actor, pk):
    item = IdentityChangeRequest.objects.filter(pk=pk).first()
    if item is None or not visible_request(actor, item):
        raise BusinessError(40401, "Not found", 404)
    return _request_data(item)


@transaction.atomic
def edit_change_request(actor, pk, data):
    item = IdentityChangeRequest.objects.select_for_update().filter(pk=pk).first()
    if item is None or not visible_request(actor, item):
        raise BusinessError(40401, "Not found", 404)
    if item.status != "draft":
        raise BusinessError(40902, "Only a draft can be edited")
    if item.submitted_by_id != actor.id:
        raise BusinessError(40301, "Only the applicant can edit the draft", 403)
    doc_type, country, number, document_hash, last4 = bind(
        data["document_type"], data["document_country"], data["document_number"]
    )
    item.new_document_type = doc_type
    item.new_document_country = country
    item.new_document_number_enc = encrypt(number)
    item.new_document_hash = document_hash
    item.new_document_last4 = last4
    item.save(
        update_fields=[
            "new_document_type",
            "new_document_country",
            "new_document_number_enc",
            "new_document_hash",
            "new_document_last4",
        ]
    )
    return _request_data(item)


@transaction.atomic
def submit_change_request(actor, pk):
    item = IdentityChangeRequest.objects.select_for_update().filter(pk=pk).first()
    if item is None or not visible_request(actor, item):
        raise BusinessError(40401, "Not found", 404)
    if item.submitted_by_id != actor.id:
        raise BusinessError(40301, "Only the applicant can submit", 403)
    if item.status != "draft":
        raise BusinessError(40902, "This request is not a draft")
    item.status = "submitted"
    item.save(update_fields=["status"])
    audit(
        actor,
        "identity.change.submitted",
        "identity_change_request",
        item.id,
        scope={"target_user_id": item.user_id},
    )
    return _request_data(item)


@transaction.atomic
def withdraw_change_request(actor, pk, copy_draft=False):
    """未审可取消：原申请留档 withdrawn；copy_draft 时原子复制为新草稿，
    保证同一时间仅一条待处理申请（uniq_pending_identity_change）。"""
    item = IdentityChangeRequest.objects.select_for_update().filter(pk=pk).first()
    if item is None or not visible_request(actor, item):
        raise BusinessError(40401, "Not found", 404)
    if item.submitted_by_id != actor.id:
        raise BusinessError(40301, "Only the applicant can cancel", 403)
    if item.status not in ("draft", "submitted"):
        raise BusinessError(40902, "A reviewed request cannot be cancelled here")
    item.status = "withdrawn"
    item.save(update_fields=["status"])
    replacement = None
    if copy_draft:
        replacement = IdentityChangeRequest.objects.create(
            resubmission_of=item,
            user=item.user,
            base_identity_version=item.base_identity_version,
            old_document_hash=item.old_document_hash,
            new_document_type=item.new_document_type,
            new_document_country=item.new_document_country,
            new_document_number_enc=item.new_document_number_enc,
            new_document_hash=item.new_document_hash,
            new_document_last4=item.new_document_last4,
            status="draft",
            submitted_by=actor,
        )
    audit(
        actor,
        "identity.change.withdrawn",
        "identity_change_request",
        item.id,
        scope={"target_user_id": item.user_id},
        detail={"replacement_id": replacement.id if replacement else None},
    )
    return _request_data(replacement or item)


@transaction.atomic
def review_change_request(actor, pk, action, comment, version):
    """approve 原子切换：换绑新证件、释放旧号、递增 identity_version 与会话版本；
    证件/类型/国家变更只能经批准路径写入（PG 触发器二次守卫）。"""
    if action not in ("approve", "return", "reject"):
        raise BusinessError(40001, "Unknown action", 400)
    if action in ("return", "reject") and not (comment or "").strip():
        raise BusinessError(40001, "A reason is required", 400)
    item = IdentityChangeRequest.objects.select_for_update().filter(pk=pk).first()
    if item is None:
        raise BusinessError(40401, "Not found", 404)
    _reviewer_scope(actor, item.user)
    if item.submitted_by_id == actor.id or item.user_id == actor.id:
        raise BusinessError(40303, "You cannot review this request", 403)
    if item.status != "submitted":
        raise BusinessError(40902, "This request is not awaiting review")
    target = User.objects.select_for_update().get(pk=item.user_id)
    profile = _lock_profile(target.id)
    if (
        profile.identity_version != version
        or profile.identity_version != item.base_identity_version
    ):
        # 07 §证件与代建：版本冲突整体回滚。
        raise BusinessError(40906, "Identity has changed, reload the request")
    now = timezone.now()
    item.status = {"approve": "approved", "return": "returned", "reject": "rejected"}[
        action
    ]
    item.reviewer = actor
    item.comment = (comment or "").strip() or None
    item.reviewed_at = now
    if action == "approve":
        if (
            Profile.objects.filter(
                document_hash=item.new_document_hash, is_deleted=False
            )
            .exclude(pk=profile.pk)
            .exists()
        ):
            raise BusinessError(40904, "This document is already bound to an account")
        # 先批准申请行再改档案：PG 守卫只认状态已为 approved 的匹配申请。
        item.save(update_fields=["status", "reviewer", "comment", "reviewed_at"])
        profile.document_type = item.new_document_type
        profile.document_country = item.new_document_country
        profile.document_number_enc = item.new_document_number_enc
        profile.document_hash = item.new_document_hash
        profile.document_last4 = item.new_document_last4
        profile.identity_version = profile.identity_version + 1
        profile.identity_change_request = item
        profile.save(
            update_fields=[
                "document_type",
                "document_country",
                "document_number_enc",
                "document_hash",
                "document_last4",
                "identity_version",
                "identity_change_request",
                "updated_at",
            ]
        )
        # 撤销旧会话：证件变更后旧 token 不得继续代表本人。
        target.token_version += 1
        target.save(update_fields=["token_version", "updated_at"])
    else:
        item.save(update_fields=["status", "reviewer", "comment", "reviewed_at"])
    audit(
        actor,
        f"identity.change.{item.status}",
        "identity_change_request",
        item.id,
        scope={"target_user_id": item.user_id},
        detail={
            "base_identity_version": item.base_identity_version,
            "identity_version": profile.identity_version,
            "comment": item.comment or "",
        },
    )
    return _request_data(item)


def list_change_requests(actor):
    items = IdentityChangeRequest.objects.select_related("user").order_by("-id")
    rows = [item for item in items if visible_request(actor, item)]
    return [_request_data(item) for item in rows]

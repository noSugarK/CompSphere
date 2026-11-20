from django.db.models import Count, Q

from apps.accounts.models import User
from apps.awards.models import AwardRecord
from apps.competitions.models import Competition, Edition
from apps.orgs.models import Organization
from apps.rbac.services import grants
from apps.registrations.models import Registration

STATS_CODES = ("stats:read_platform", "stats:read_competition")


def may_view_dashboard(actor):
    return any(code in g["permissions"] for g in grants(actor) for code in STATS_CODES)


def _platform(rows):
    return any(
        "stats:read_platform" in g["permissions"]
        and g["scope_type"] == "global"
        and g["role"] == "platform_admin"
        for g in rows
    )


def dashboard(actor):
    """01 §3.8 P0 计数卡片：只统计已提交轮次（草稿不进分母），
    按 02 的届次/赛事作用域过滤；单位维度统计属 P1，不在此。"""
    rows = grants(actor)
    registrations = Registration.objects.filter(
        is_deleted=False, current_submission_no__isnull=False
    )
    awarded = AwardRecord.objects.filter(is_deleted=False)
    platform = _platform(rows)
    if not platform:
        scope = Q(pk__in=[])
        for g in rows:
            if "stats:read_competition" not in g["permissions"]:
                continue
            if g["scope_type"] == "edition":
                scope |= Q(edition_id=g["scope_id"])
            elif g["scope_type"] == "competition":
                scope |= Q(edition__competition_id=g["scope_id"])
        registrations = registrations.filter(scope)
        awarded = awarded.filter(scope)
    reviewed_count = registrations.filter(
        status__in=("approved", "rejected", "returned", "withdrawn")
    ).count()
    approved_count = registrations.filter(status="approved").count()
    data = {
        "registrations": registrations.count(),
        "approved": approved_count,
        # 通过率 = 已通过 / 已出结果；无结果时为 null。
        "approval_rate": (
            round(approved_count / reviewed_count, 4) if reviewed_count else None
        ),
        "awarded": awarded.values("registration").distinct().count(),
        "by_offering": [
            {
                "event_name": row["offering__event__name"],
                "group_name": row["offering__group__name"],
                "submitted": row["submitted"],
                "approved": row["approved"],
            }
            for row in registrations.values(
                "offering__event__name", "offering__group__name"
            )
            .annotate(
                submitted=Count("id"),
                approved=Count("id", filter=Q(status="approved")),
            )
            .order_by("offering__event__name", "offering__group__name")
        ],
    }
    if platform:
        # 平台盘子仅 stats:read_platform 输出。
        data.update(
            {
                "users": User.objects.filter(status="active", is_deleted=False).count(),
                "organizations": Organization.objects.filter(
                    status="active", is_deleted=False
                ).count(),
                "competitions": Competition.objects.filter(is_deleted=False).count(),
                "editions": Edition.objects.filter(is_deleted=False).count(),
            }
        )
    return data

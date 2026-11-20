from django.db.models import Q
from django.utils.dateparse import parse_date

from apps.audit.models import AuditLog
from apps.competitions.models import Edition
from apps.orgs.models import Organization
from apps.rbac.services import grants
from core.exceptions import BusinessError


def visible_logs(actor):
    """02 audit:read：本单位相关 / 本赛事相关 / 平台全量。可见性按写入时的
    scope 键匹配；未写 scope 键的行（如 development seed）仅平台可见。
    ponytail: 按 scope 匹配而非逐表反查对象归属；新增审计写入方必须带 scope。"""
    conditions = Q()
    seen = False
    for g in grants(actor):
        if "audit:read" not in g["permissions"]:
            continue
        seen = True
        if g["scope_type"] == "global" and g["role"] == "platform_admin":
            return AuditLog.objects.all()
        if g["scope_type"] == "edition":
            # 届次读者同时看到该届次所属赛事的赛事级事件。
            competition_ids = list(
                Edition.objects.filter(pk=g["scope_id"]).values_list(
                    "competition_id", flat=True
                )
            )
            conditions |= (
                Q(scope__edition_id=g["scope_id"])
                | Q(scope__competition_id__in=competition_ids)
                | Q(resource="edition", resource_id=str(g["scope_id"]))
            )
        elif g["scope_type"] == "competition":
            conditions |= Q(scope__competition_id=g["scope_id"]) | Q(
                resource="competition", resource_id=str(g["scope_id"])
            )
        elif g["scope_type"] == "org":
            parent = Organization.objects.filter(
                pk=g["scope_id"], is_deleted=False, status="active"
            ).first()
            if parent:
                tree = (
                    Organization.objects.filter(pk=parent.pk)
                    if g["role"] == "team_coach"
                    else Organization.objects.filter(
                        path__startswith=parent.path,
                        is_deleted=False,
                        status="active",
                    )
                )
                conditions |= Q(
                    scope__org_id__in=list(tree.values_list("id", flat=True))
                )
    if not seen:
        raise BusinessError(40301, "Permission denied", 403)
    return AuditLog.objects.filter(conditions)


def query(actor, *, actor_id=None, resource=None, date_from=None, date_to=None):
    logs = visible_logs(actor)
    if actor_id is not None:
        logs = logs.filter(actor_id=actor_id)
    if resource:
        logs = logs.filter(resource=resource)
    if date_from:
        parsed = parse_date(date_from)
        if parsed is None:
            raise BusinessError(40001, "Expected a YYYY-MM-DD date", 400)
        logs = logs.filter(created_at__date__gte=parsed)
    if date_to:
        parsed = parse_date(date_to)
        if parsed is None:
            raise BusinessError(40001, "Expected a YYYY-MM-DD date", 400)
        logs = logs.filter(created_at__date__lte=parsed)
    return logs.order_by("-id")

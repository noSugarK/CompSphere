from django.db.models import Q
from rest_framework.permissions import BasePermission

from apps.orgs.models import Organization
from apps.rbac.models import Role, UserRole
from core.exceptions import BusinessError


def grant_participant(user):
    role = Role.objects.filter(code="participant").first()
    if role is None:
        raise BusinessError(
            50301, "Account registration is temporarily unavailable", 503
        )
    return UserRole.objects.create(
        user=user, role=role, scope_type="global", scope_id=None
    )


def grants(user):
    return [
        {
            "role": g.role.code,
            "scope_type": g.scope_type,
            "scope_id": g.scope_id,
            "permissions": sorted(p.code for p in g.role.permissions.all()),
        }
        for g in UserRole.objects.filter(user=user)
        .select_related("role")
        .prefetch_related("role__permissions")
    ]


def has_perm(user, permission, *, org_id=None, edition=None, own=False):
    if not user or not user.is_active:
        return False
    for g in grants(user):
        if permission not in g["permissions"]:
            continue
        if g["scope_type"] == "global":
            # Participant's global grant is a personal grant, never cross-object authority.
            if g["role"] == "platform_admin" or own:
                return True
        elif g["scope_type"] == "edition" and edition and g["scope_id"] == edition.id:
            return True
        elif (
            g["scope_type"] == "competition"
            and edition
            and g["scope_id"] == edition.competition_id
        ):
            return True
        elif g["scope_type"] == "org" and org_id:
            parent = Organization.objects.filter(
                pk=g["scope_id"], is_deleted=False, status="active"
            ).first()
            child = Organization.objects.filter(
                pk=org_id, is_deleted=False, status="active"
            ).first()
            if (
                parent
                and child
                and (
                    child.pk == parent.pk
                    or (
                        g["role"] != "team_coach" and child.path.startswith(parent.path)
                    )
                )
            ):
                return True
    return False


def require_perm(user, permission, **scope):
    if not has_perm(user, permission, **scope):
        raise BusinessError(40301, "Permission denied", 403)


def org_filter(user, permission, field="org_id"):
    ids: list[int] = []
    for g in grants(user):
        if permission not in g["permissions"]:
            continue
        if g["scope_type"] == "global" and g["role"] == "platform_admin":
            return Q()
        if g["scope_type"] == "org":
            parent = Organization.objects.filter(
                pk=g["scope_id"], is_deleted=False, status="active"
            ).first()
            if parent:
                ids.extend(
                    Organization.objects.filter(
                        path__startswith=parent.path, is_deleted=False, status="active"
                    ).values_list("id", flat=True)
                    if g["role"] != "team_coach"
                    else [parent.id]
                )
    return Q(**{f"{field}__in": ids})


def registration_filter(user, permission):
    result = Q(pk__in=[])
    for g in grants(user):
        if permission not in g["permissions"]:
            continue
        if g["scope_type"] == "global" and g["role"] == "platform_admin":
            return Q()
        if g["scope_type"] == "org":
            result |= org_filter(user, permission)
        if g["scope_type"] == "edition":
            result |= Q(edition_id=g["scope_id"])
        if g["scope_type"] == "competition":
            result |= Q(edition__competition_id=g["scope_id"])
    return result


class ScopedRolePermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_active:
            return False
        required = getattr(view, "required_perm", None)
        return not required or any(
            required in g["permissions"] for g in grants(request.user)
        )


def prevent_self_review(actor, submitted_by_id, member_ids=()):
    if actor.id == submitted_by_id or actor.id in member_ids:
        raise BusinessError(40303, "You cannot review your own submission", 403)

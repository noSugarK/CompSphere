from django.db import transaction

from apps.rbac.models import Permission, Role

PARTICIPANT = [
    "profile:read_own",
    "profile:update_own",
    "profile:request_identity_change",
    "org:apply_create",
    "registration:create",
    "registration:read_own",
    "registration:update",
    "registration:withdraw",
    "registration:cancel_review",
    "registration:delete_draft",
    "team:leave_own",
    "team:request_transfer",
]
COACH = [
    "profile:read_own",
    "profile:update_own",
    "profile:read",
    "org:read",
    "org:apply_create",
    "team:read",
    "competition:read",
    "edition:read",
    "event:read",
    "group:read",
    "registration:create",
    "registration:read_own",
    "registration:update",
    "registration:withdraw",
    "registration:cancel_review",
    "registration:delete_draft",
]
ORG_ADMIN = [
    "profile:read_own",
    "profile:update_own",
    "profile:read",
    "profile:update",
    "profile:review",
    "org:read",
    "org:update",
    "org:manage_members",
    "org:apply_create",
    "team:read",
    "team:create",
    "team:update",
    "team:manage_members",
    "team:dissolve",
    "team:review",
    "team:request_season_registration",
    "user:read",
    "user:create",
    "user:provision",
    "user:reset_student_password",
    "user:import",
    "registration:read_history",
    "audit:read",
]
EVENT_ADMIN = [
    "profile:read_own",
    "profile:update_own",
    "competition:read",
    "competition:update",
    "competition:publish",
    "competition:archive",
    "competition:manage_units",
    "edition:create",
    "edition:read",
    "edition:update",
    "edition:publish",
    "edition:close",
    "event:create",
    "event:read",
    "event:update",
    "event:enable_disable",
    "group:create",
    "group:read",
    "group:update",
    "group:enable_disable",
    "registration:read",
    "registration:read_history",
    "registration:export",
    "approval:review_single",
    "approval:batch_review",
    "approval:read_records",
    "approval:reject_approved",
    "roster:publish",
    "roster:unpublish",
    "award:config",
    "award:read",
    "award:manage_roster",
    "award:submit_roster",
    "award:approve_roster",
    "notice:publish",
    "audit:read",
]
REVIEWER = [
    "profile:read_own",
    "profile:update_own",
    "competition:read",
    "edition:read",
    "event:read",
    "group:read",
    "registration:read",
    "registration:read_history",
    "approval:review_single",
    "approval:read_records",
    "approval:reject_approved",
]
PLATFORM_EXTRA = [
    "team:review_create",
    "team:review_season_registration",
    "team:review_transfer",
    "season:read",
    "season:create",
    "season:update",
    "season:activate",
    "season:archive",
    "season:set_current",
    "user:assign_role",
    "user:disable",
    "user:export",
    "competition:create",
    "competition:manage_admins",
    "system:manage_roles",
    "system:manage_settings",
    "system:backup",
]
ROLE_PERMISSIONS = {
    "participant": PARTICIPANT,
    "team_coach": COACH,
    "org_admin": ORG_ADMIN,
    "competition_admin": EVENT_ADMIN,
    "reviewer": REVIEWER,
}
ROLE_PERMISSIONS["platform_admin"] = sorted(
    set(PLATFORM_EXTRA + sum(ROLE_PERMISSIONS.values(), []))
)


@transaction.atomic
def seed_rbac():
    for code in sorted(set(sum(ROLE_PERMISSIONS.values(), []))):
        resource, action = code.split(":")
        Permission.objects.update_or_create(
            code=code, defaults={"name": code, "resource": resource, "action": action}
        )
    for code, permissions in ROLE_PERMISSIONS.items():
        role, _ = Role.objects.get_or_create(code=code, defaults={"name": code})
        role.permissions.set(Permission.objects.filter(code__in=permissions))

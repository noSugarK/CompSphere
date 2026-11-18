from apps.audit.models import AuditLog


def audit(actor, action, resource, obj_id, scope=None, detail=None):
    # Callers provide only server-selected IDs/versions, never raw payloads or secrets.
    AuditLog.objects.create(
        actor=actor,
        action=action,
        resource=resource,
        resource_id=str(obj_id),
        scope=scope or {},
        detail=detail or {},
    )

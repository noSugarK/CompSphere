from uuid import uuid4

from django.db import transaction

from apps.audit.services import audit
from apps.competitions.models import Competition
from apps.rbac.services import grants, require_perm
from core.exceptions import BusinessError


def managed_competitions(user):
    queryset = Competition.objects.filter(is_deleted=False).order_by("-id")
    competition_ids = []
    for grant in grants(user):
        if "competition:read" not in grant["permissions"]:
            continue
        if grant["scope_type"] == "global" and grant["role"] == "platform_admin":
            return queryset
        if grant["scope_type"] == "competition":
            competition_ids.append(grant["scope_id"])
    if not competition_ids:
        raise BusinessError(40301, "Competition registry access is not granted", 403)
    return queryset.filter(pk__in=competition_ids)


@transaction.atomic
def create_competition(actor, data):
    """Create a private draft without assigning roles or creating an edition."""
    require_perm(actor, "competition:create")
    item = Competition.objects.create(
        public_code=f"CMP-{uuid4().hex[:24].upper()}", **data
    )
    audit(actor, "competition.created", "competition", item.id)
    return item

"""Explicit synthetic fixtures for development and repeatable integration checks."""

import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.services import audit
from apps.competitions.models import Competition, Edition, Season
from apps.events.models import Event, EventType, Offering
from apps.groups.models import Group
from apps.orgs.models import Organization, OrganizationMember
from apps.profiles.models import Profile
from apps.rbac.models import Role, UserRole
from apps.rbac.seed import seed_rbac
from apps.teams.models import (
    SeasonRegistration,
    Team,
    TeamChangeRequest,
    TeamMember,
    TeamNumber,
)
from core.crypto import encrypt


@transaction.atomic
def create_development_data(password):
    seed_rbac()
    if User.objects.filter(email__endswith="@dev.example").exists():
        raise ValueError(
            "Development fixtures already exist; no credentials or data were overwritten."
        )
    now = timezone.now()
    school = Organization.add_root(name="Development School", code="DEV-SCHOOL")
    other_school = Organization.add_root(
        name="Other Development School", code="DEV-OTHER"
    )
    season = Season.objects.create(
        code="DEV-SEASON",
        name="Development season",
        starts_on=now.date() - timedelta(days=30),
        ends_on=now.date() + timedelta(days=365),
        status="active",
        is_default=True,
    )
    competition = Competition.objects.create(
        public_code="DEV-ROBOTICS",
        name="机器人公开赛 · 开发环境",
        summary="仅用于本地开发验证的合成赛事。",
        status="published",
    )
    edition = Edition.objects.create(
        competition=competition,
        season=season,
        year=now.year,
        name="开发联调场次",
        status="published",
        enroll_start=now - timedelta(days=1),
        enroll_end=now + timedelta(days=30),
        start_date=now + timedelta(days=40),
        end_date=now + timedelta(days=41),
        venue="Development venue",
    )
    event_type, _ = EventType.objects.get_or_create(
        code="V5RC", defaults={"name": "VEX V5 Robotics"}
    )
    event = Event.objects.create(
        edition=edition,
        code=event_type,
        name="V5RC",
        min_members=1,
        max_members=4,
        coach_required=True,
    )
    group = Group.objects.create(
        edition=edition,
        code="HS",
        name="高中组",
        school_level="HS",
        enrollment_type="both",
    )
    offering = Offering.objects.create(edition=edition, event=event, group=group)
    accounts = {}
    definitions = [
        ("platform", "platform_admin", None),
        ("manager", "org_admin", school),
        ("coach", "team_coach", school),
        ("student", "participant", school),
        ("reviewer", "reviewer", None),
        ("organizer", "competition_admin", None),
        ("outsider", "participant", other_school),
    ]
    for index, (name, role_code, org) in enumerate(definitions):
        user = User.objects.create_user(
            email=f"{name}@dev.example",
            password=password,
            status="active",
            email_verified_at=now,
        )
        person_type = (
            "coach"
            if name == "coach"
            else "participant"
            if name in ("student", "outsider")
            else "staff"
        )
        document = f"DEVTEST{index:06d}" if person_type == "participant" else None
        digest = (
            hmac.new(
                settings.DOC_HASH_PEPPER.encode(),
                f"passport|US|{document}".encode(),
                hashlib.sha256,
            ).hexdigest()
            if document
            else None
        )
        Profile.objects.create(
            user=user,
            real_name=f"Dev {name}",
            person_type=person_type,
            school_level="HS" if document else None,
            grade="高一" if document else None,
            document_type="passport" if document else None,
            document_country="US" if document else None,
            document_number_enc=encrypt(document) if document else None,
            document_hash=digest,
            document_last4=document[-4:] if document else None,
        )
        if org:
            OrganizationMember.objects.create(
                org=org,
                user=user,
                member_type="teacher" if name == "coach" else "student",
            )
        scope = (
            "org"
            if role_code in ("org_admin", "team_coach")
            else "edition"
            if role_code in ("reviewer", "competition_admin")
            else "global"
        )
        UserRole.objects.create(
            user=user,
            role=Role.objects.get(code=role_code),
            scope_type=scope,
            scope_id=org.id
            if scope == "org"
            else edition.id
            if scope == "edition"
            else None,
        )
        accounts[name] = user
    number = TeamNumber.objects.create(code="DEV1024A", org=school)
    team = Team.objects.create(
        team_number=number,
        event_code=event_type,
        name="逐光开发队",
        org=school,
        coach=accounts["coach"],
        captain=accounts["student"],
    )
    proposal = {
        "name": team.name,
        "coach_id": accounts["coach"].id,
        "captain_id": accounts["student"].id,
        "members": [{"user_id": accounts["student"].id, "role": "captain"}],
    }
    revision = TeamChangeRequest.objects.create(
        team=team,
        org=school,
        team_code=number.code,
        event_code=event_type,
        request_kind="create",
        registration_season=season,
        proposal_enc=encrypt(proposal),
        status="approved",
        submitted_by=accounts["manager"],
        reviewer=accounts["platform"],
        reviewed_at=now,
    )
    team.approved_revision = revision
    team.save(update_fields=["approved_revision"])
    TeamMember.objects.create(team=team, user=accounts["student"], role="captain")
    SeasonRegistration.objects.create(
        team=team,
        season=season,
        status="approved",
        proposal_enc=encrypt({"team_revision_id": revision.id}),
        submitted_by=accounts["manager"],
        reviewer=accounts["platform"],
        reviewed_at=now,
        comment="Synthetic development fixture",
    )
    audit(accounts["platform"], "development.seeded", "competition", competition.id)
    return {
        "accounts": accounts,
        "school": school,
        "other_school": other_school,
        "season": season,
        "competition": competition,
        "edition": edition,
        "offering": offering,
        "team": team,
    }

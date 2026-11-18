from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import BusinessModel


class TeamNumber(models.Model):
    code = models.CharField(max_length=32, unique=True)
    org = models.ForeignKey("orgs.Organization", on_delete=models.PROTECT)

    class Meta:
        db_table = "team_numbers"


class Team(BusinessModel):
    team_number = models.ForeignKey(TeamNumber, on_delete=models.PROTECT)
    event_code = models.ForeignKey(
        "events.EventType", db_column="event_code", on_delete=models.PROTECT
    )
    name = models.CharField(max_length=128)
    org = models.ForeignKey("orgs.Organization", on_delete=models.PROTECT)
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    captain = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    membership_version = models.PositiveIntegerField(default=1)
    approved_revision = models.ForeignKey(
        "TeamChangeRequest", on_delete=models.PROTECT, null=True, related_name="+"
    )
    status = models.CharField(max_length=16, default="active")

    class Meta:
        db_table = "teams"
        constraints = [
            models.UniqueConstraint(
                fields=["team_number", "event_code"], name="unique_team_identity"
            )
        ]


class TeamChangeRequest(models.Model):
    resubmission_of = models.ForeignKey("self", on_delete=models.PROTECT, null=True)
    team = models.ForeignKey(Team, on_delete=models.PROTECT, null=True)
    org = models.ForeignKey("orgs.Organization", on_delete=models.PROTECT)
    team_code = models.CharField(max_length=32)
    event_code = models.ForeignKey(
        "events.EventType", db_column="event_code", on_delete=models.PROTECT
    )
    request_kind = models.CharField(max_length=16)
    registration_season = models.ForeignKey(
        "competitions.Season", on_delete=models.PROTECT, null=True
    )
    base_revision = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, related_name="+"
    )
    base_membership_version = models.PositiveIntegerField(default=1)
    proposal_enc = models.BinaryField()
    status = models.CharField(max_length=16, default="draft")
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    comment = models.TextField(default="")
    reviewed_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "team_change_requests"
        constraints = [
            models.UniqueConstraint(
                fields=["team"],
                condition=models.Q(
                    request_kind="update", status__in=["draft", "submitted"]
                ),
                name="uniq_team_pending_change",
            ),
            models.UniqueConstraint(
                fields=["team_code", "event_code"],
                condition=models.Q(status__in=["draft", "submitted"]),
                name="uniq_team_pending_code",
            ),
            models.CheckConstraint(
                condition=models.Q(reviewer__isnull=True)
                | ~models.Q(reviewer=models.F("submitted_by")),
                name="team_no_self_review",
            ),
        ]


class TeamMember(models.Model):
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    role = models.CharField(max_length=16, default="member")
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "team_members"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(left_at__isnull=True),
                name="uniq_current_team_member",
            )
        ]


class SeasonRegistration(models.Model):
    team = models.ForeignKey(
        Team, on_delete=models.PROTECT, related_name="season_registrations"
    )
    season = models.ForeignKey("competitions.Season", on_delete=models.PROTECT)
    resubmission_of = models.ForeignKey("self", on_delete=models.PROTECT, null=True)
    status = models.CharField(max_length=16, default="draft")
    proposal_enc = models.BinaryField()
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True)
    comment = models.TextField(default="")
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    revoked_at = models.DateTimeField(null=True)
    revoke_reason = models.TextField(null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "team_season_registrations"
        constraints = [
            models.UniqueConstraint(
                fields=["team", "season"],
                condition=models.Q(status__in=["draft", "submitted", "approved"]),
                name="uniq_live_team_season_registration",
            ),
            models.CheckConstraint(
                condition=models.Q(reviewer__isnull=True)
                | ~models.Q(reviewer=models.F("submitted_by")),
                name="season_license_no_self_review",
            ),
        ]

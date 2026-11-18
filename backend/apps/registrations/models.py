from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import BusinessModel


class Registration(BusinessModel):
    batch_no = models.CharField(max_length=40, unique=True)
    edition = models.ForeignKey("competitions.Edition", on_delete=models.PROTECT)
    offering = models.ForeignKey("events.Offering", on_delete=models.PROTECT)
    enrollment_kind = models.CharField(max_length=16)
    individual_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    team = models.ForeignKey("teams.Team", on_delete=models.PROTECT, null=True)
    org = models.ForeignKey("orgs.Organization", on_delete=models.PROTECT)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    coach_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    # Working contact/form data is encrypted, unlike non-sensitive status and references.
    contact_name = models.CharField(max_length=64, null=True)
    contact_phone = models.CharField(max_length=20, default="")
    contact_email = models.EmailField(null=True)
    form_data = models.JSONField(default=dict)
    consent_snapshot = models.JSONField(default=dict)
    draft_enc = models.BinaryField()
    selected_school_level = models.CharField(max_length=8, null=True)
    status = models.CharField(max_length=20, default="draft")
    current_submission_no = models.PositiveIntegerField(null=True)
    approved_submission_no = models.PositiveIntegerField(null=True)
    return_round = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(null=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "registrations"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    team__isnull=False,
                    individual_user__isnull=True,
                    enrollment_kind="team",
                )
                | models.Q(
                    team__isnull=True,
                    individual_user__isnull=False,
                    enrollment_kind="individual",
                ),
                name="registration_subject_xor",
            ),
            models.UniqueConstraint(
                fields=["edition", "team", "offering"],
                condition=models.Q(enrollment_kind="team", is_deleted=False)
                & ~models.Q(status__in=["draft", "withdrawn"]),
                name="uniq_reg_team",
            ),
            models.UniqueConstraint(
                fields=["edition", "individual_user", "offering"],
                condition=models.Q(enrollment_kind="individual", is_deleted=False)
                & ~models.Q(status__in=["draft", "withdrawn"]),
                name="uniq_reg_individual",
            ),
        ]


class RegistrationSubmission(models.Model):
    registration = models.ForeignKey(
        Registration, on_delete=models.PROTECT, related_name="submissions"
    )
    submission_no = models.PositiveIntegerField()
    team = models.ForeignKey("teams.Team", on_delete=models.PROTECT, null=True)
    team_revision = models.ForeignKey(
        "teams.TeamChangeRequest", on_delete=models.PROTECT, null=True
    )
    approval_mode = models.CharField(max_length=16, default="single")
    selected_school_level = models.CharField(max_length=8, null=True)
    snapshot_enc = models.BinaryField()
    access_snapshot = models.JSONField(default=dict)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    submitted_at = models.DateTimeField(default=timezone.now)
    cancelled_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "registration_submissions"
        constraints = [
            models.UniqueConstraint(
                fields=["registration", "submission_no"],
                name="unique_registration_submission",
            )
        ]


class RegistrationMember(models.Model):
    registration = models.ForeignKey(
        Registration, on_delete=models.PROTECT, related_name="submitted_members"
    )
    submission_no = models.PositiveIntegerField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True
    )
    snapshot_enc = models.BinaryField()
    public_info = models.JSONField()
    document_hash = models.CharField(max_length=64, null=True)
    role = models.CharField(max_length=16, default="member")
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "registration_members"
        constraints = [
            models.UniqueConstraint(
                fields=["registration", "submission_no", "user"],
                name="uniq_registration_member_user",
            ),
            models.UniqueConstraint(
                fields=["registration", "submission_no", "document_hash"],
                condition=models.Q(document_hash__isnull=False),
                name="uniq_registration_member_identity",
            ),
        ]


class ApprovalRecord(models.Model):
    registration = models.ForeignKey(
        Registration, on_delete=models.PROTECT, related_name="approval_records"
    )
    submission_no = models.PositiveIntegerField()
    step = models.CharField(max_length=16, default="final")
    round_no = models.PositiveIntegerField(default=1)
    action = models.CharField(max_length=16)
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    comment = models.TextField(default="")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "approval_records"


class SeasonStudentTeamBinding(models.Model):
    season = models.ForeignKey("competitions.Season", on_delete=models.PROTECT)
    event_code = models.ForeignKey(
        "events.EventType", db_column="event_code", on_delete=models.PROTECT
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    original_team = models.ForeignKey(
        "teams.Team", on_delete=models.PROTECT, related_name="+"
    )
    current_team = models.ForeignKey(
        "teams.Team", on_delete=models.PROTECT, related_name="+"
    )
    source_registration = models.ForeignKey(Registration, on_delete=models.PROTECT)
    source_submission_no = models.PositiveIntegerField()
    binding_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "season_student_team_bindings"
        constraints = [
            models.UniqueConstraint(
                fields=["season", "event_code", "user"],
                name="unique_season_student_binding",
            )
        ]

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import BusinessModel


class IdentityChangeRequest(models.Model):
    """04 §identity_change_requests：草稿→提交→批准/退回/驳回/撤回。
    服务器冻结 base_identity_version、旧绑定与新证件密文。"""

    STATUSES = ("draft", "submitted", "approved", "returned", "rejected", "withdrawn")
    resubmission_of = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, related_name="resubmissions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    base_identity_version = models.PositiveIntegerField()
    old_document_hash = models.CharField(max_length=64, null=True)
    new_document_type = models.CharField(max_length=16)
    new_document_country = models.CharField(max_length=2)
    new_document_number_enc = models.BinaryField()
    new_document_hash = models.CharField(max_length=64)
    new_document_last4 = models.CharField(max_length=4)
    status = models.CharField(max_length=16, default="draft")
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    comment = models.TextField(null=True)
    reviewed_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "identity_change_requests"
        constraints = [
            models.CheckConstraint(
                condition=Q(new_document_type__in=("id_card", "passport"))
                & (~Q(new_document_type="id_card") | Q(new_document_country="CN")),
                name="identity_change_country_matches_type",
            ),
            models.CheckConstraint(
                condition=~Q(status__in=("approved", "returned", "rejected"))
                | Q(reviewer__isnull=False, reviewed_at__isnull=False),
                name="identity_change_review_metadata",
            ),
            models.CheckConstraint(
                condition=~Q(status__in=("returned", "rejected"))
                | Q(comment__isnull=False),
                name="identity_change_decision_comment",
            ),
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status__in=("draft", "submitted")),
                name="uniq_pending_identity_change",
            ),
        ]


class Profile(BusinessModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="profile"
    )
    real_name = models.CharField(max_length=64)
    gender = models.CharField(max_length=10, null=True)
    birth_date = models.DateField(null=True)
    document_type = models.CharField(max_length=16, null=True)
    document_country = models.CharField(max_length=2, null=True)
    document_number_enc = models.BinaryField(null=True)
    document_hash = models.CharField(max_length=64, null=True, unique=True)
    document_last4 = models.CharField(max_length=4, null=True)
    identity_version = models.PositiveIntegerField(default=0)
    identity_change_request = models.ForeignKey(
        "profiles.IdentityChangeRequest",
        on_delete=models.PROTECT,
        null=True,
        related_name="+",
    )
    photo_storage_key = models.CharField(max_length=512, null=True)
    person_type = models.CharField(max_length=16, default="participant")
    school_level = models.CharField(max_length=8, null=True)
    grade = models.CharField(max_length=32, null=True)
    student_no = models.CharField(max_length=64, null=True)
    staff_no = models.CharField(max_length=64, null=True)
    title = models.CharField(max_length=64, null=True)

    class Meta:
        db_table = "user_profiles"

from django.conf import settings
from django.db import models

from core.models import BusinessModel


class Award(BusinessModel):
    edition = models.ForeignKey(
        "competitions.Edition", on_delete=models.PROTECT, related_name="awards"
    )
    # NULL = 届次通用奖项，04 §awards；评奖口径与开放组合一致（届次×赛项×组别）。
    offering = models.ForeignKey(
        "events.Offering", on_delete=models.PROTECT, null=True, related_name="awards"
    )
    rank_level = models.CharField(max_length=16)
    name = models.CharField(max_length=64)
    quota = models.PositiveIntegerField(null=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = "awards"
        constraints = [
            models.UniqueConstraint(
                fields=["edition", "offering", "name"],
                name="unique_edition_award_name",
                nulls_distinct=False,
            )
        ]


class AwardRoster(BusinessModel):
    edition = models.ForeignKey(
        "competitions.Edition", on_delete=models.PROTECT, related_name="award_rosters"
    )
    offering = models.ForeignKey(
        "events.Offering", on_delete=models.PROTECT, null=True, related_name="rosters"
    )
    status = models.CharField(max_length=20, default="editing")
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        related_name="+",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True)
    # 解锁编辑递增；异步回调必须匹配当前版本（04 §award_rosters）。
    version = models.PositiveIntegerField(default=1)
    lock_note = models.TextField(null=True)

    class Meta:
        db_table = "award_rosters"
        constraints = [
            models.UniqueConstraint(
                fields=["edition", "offering"],
                name="unique_edition_roster",
                nulls_distinct=False,
            )
        ]


class AwardRecord(BusinessModel):
    edition = models.ForeignKey(
        "competitions.Edition", on_delete=models.PROTECT, related_name="award_records"
    )
    roster = models.ForeignKey(
        AwardRoster, on_delete=models.CASCADE, related_name="records"
    )
    award = models.ForeignKey(Award, on_delete=models.PROTECT, related_name="records")
    registration = models.ForeignKey(
        "registrations.Registration", on_delete=models.PROTECT, related_name="awards"
    )
    submission_no = models.PositiveIntegerField()
    # 冗余自报名，导入对账与公示读取都靠它，不回查可变字段（04 §award_records）。
    recipient_kind = models.CharField(max_length=16)
    batch_no = models.CharField(max_length=40)

    class Meta:
        db_table = "award_records"
        constraints = [
            models.UniqueConstraint(
                fields=["roster", "registration"],
                condition=models.Q(is_deleted=False),
                name="uniq_current_award_registration",
            )
        ]

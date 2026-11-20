from rest_framework import serializers

from core.constants import RANK_LEVELS, ROSTER_STATES
from core.serializers import StrictSerializer


class AwardDraft(StrictSerializer):
    offering_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    rank_level = serializers.ChoiceField(choices=RANK_LEVELS)
    name = serializers.CharField(max_length=64)
    quota = serializers.IntegerField(
        min_value=1, max_value=2147483647, required=False, allow_null=True
    )
    sort_order = serializers.IntegerField(
        min_value=0, max_value=2147483647, required=False
    )


class AwardPatch(StrictSerializer):
    rank_level = serializers.ChoiceField(choices=RANK_LEVELS, required=False)
    name = serializers.CharField(max_length=64, required=False)
    quota = serializers.IntegerField(
        min_value=1, max_value=2147483647, required=False, allow_null=True
    )
    sort_order = serializers.IntegerField(
        min_value=0, max_value=2147483647, required=False
    )


class Award(StrictSerializer):
    id = serializers.IntegerField()
    edition_id = serializers.IntegerField()
    offering_id = serializers.IntegerField(allow_null=True)
    rank_level = serializers.ChoiceField(choices=RANK_LEVELS)
    name = serializers.CharField()
    quota = serializers.IntegerField(allow_null=True)
    sort_order = serializers.IntegerField()


class AwardRecord(StrictSerializer):
    registration_id = serializers.IntegerField()
    award_id = serializers.IntegerField()
    submission_no = serializers.IntegerField()
    batch_no = serializers.CharField()
    team_code = serializers.CharField(allow_null=True)
    org_name = serializers.CharField()
    member_names = serializers.ListField(child=serializers.CharField())
    award_name = serializers.CharField()
    rank_level = serializers.ChoiceField(choices=RANK_LEVELS)


class AwardRoster(StrictSerializer):
    id = serializers.IntegerField(allow_null=True)
    edition_id = serializers.IntegerField()
    offering_id = serializers.IntegerField(allow_null=True)
    event_name = serializers.CharField(allow_null=True)
    group_name = serializers.CharField(allow_null=True)
    status = serializers.ChoiceField(choices=ROSTER_STATES)
    version = serializers.IntegerField()
    records = AwardRecord(many=True)


class AwardRecordTarget(StrictSerializer):
    registration_id = serializers.IntegerField(min_value=1)
    award_id = serializers.IntegerField(min_value=1)


class AwardRecordChange(StrictSerializer):
    version = serializers.IntegerField(min_value=1)
    add = serializers.ListField(
        child=AwardRecordTarget(), required=False, max_length=200
    )
    remove = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, max_length=200
    )


class RosterDecision(StrictSerializer):
    version = serializers.IntegerField(min_value=1)
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class RosterPublicationPatch(StrictSerializer):
    roster_publication = serializers.ChoiceField(choices=["open", "login", "none"])
    roster_publish_fields = serializers.ListField(
        child=serializers.CharField(max_length=32), max_length=10
    )


class EditionInfo(StrictSerializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    status = serializers.ChoiceField(choices=["draft", "published", "closed"])
    roster_publication = serializers.ChoiceField(choices=["open", "login", "none"])
    roster_publish_fields = serializers.ListField(
        child=serializers.CharField(max_length=32)
    )
    roster_published_at = serializers.DateTimeField(allow_null=True)


class PublicRosterEntry(StrictSerializer):
    # 02 §4.7：实际输出 = 服务端常量 ∩ 届次白名单，任一字段都可能被裁掉，故全部可选。
    team_code = serializers.CharField(allow_null=True, required=False)
    org_name = serializers.CharField(required=False)
    event = serializers.CharField(required=False)
    group = serializers.CharField(required=False)
    member_names = serializers.ListField(child=serializers.CharField(), required=False)
    award = serializers.CharField(required=False)


class PublicRoster(StrictSerializer):
    edition_id = serializers.IntegerField()
    edition_name = serializers.CharField()
    publish_fields = serializers.ListField(child=serializers.CharField(max_length=32))
    entries = PublicRosterEntry(many=True)

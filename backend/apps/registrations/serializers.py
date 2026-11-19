from rest_framework import serializers

from apps.teams.serializers import Member
from core.constants import REGISTRATION_STATES
from core.serializers import ReviewSerializer, StrictSerializer


class Contact(StrictSerializer):
    name = serializers.CharField(max_length=64, allow_blank=True)
    phone = serializers.CharField(max_length=20, allow_blank=True)
    email = serializers.EmailField(max_length=255, allow_null=True)


class FormData(StrictSerializer):
    project_title = serializers.CharField(max_length=200, allow_blank=True)


class Consents(StrictSerializer):
    document_usage = serializers.BooleanField()


class RegistrationCreate(StrictSerializer):
    offering_id = serializers.IntegerField(min_value=1)
    enrollment_kind = serializers.ChoiceField(choices=["individual", "team"])
    team_id = serializers.IntegerField(min_value=1, required=False)
    coach_user_id = serializers.IntegerField(min_value=1, allow_null=True)
    selected_school_level = serializers.ChoiceField(
        choices=["ES", "MS", "HS", "U"], allow_null=True
    )
    contact = Contact()
    form_data = FormData()
    consents = Consents()
    submit = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if (attrs["enrollment_kind"] == "team") != ("team_id" in attrs):
            raise serializers.ValidationError(
                "Team ID is required only for team enrollment."
            )
        return attrs


class RegistrationPatch(StrictSerializer):
    version = serializers.IntegerField(min_value=1)
    offering_id = serializers.IntegerField(min_value=1, required=False)
    coach_user_id = serializers.IntegerField(
        min_value=1, allow_null=True, required=False
    )
    selected_school_level = serializers.ChoiceField(
        choices=["ES", "MS", "HS", "U"], allow_null=True, required=False
    )
    contact = Contact(required=False)
    form_data = FormData(required=False)
    consents = Consents(required=False)


class RegistrationReview(ReviewSerializer):
    submission_no = serializers.IntegerField(min_value=1)


class BulkReviewTarget(StrictSerializer):
    registration_id = serializers.IntegerField(min_value=1)
    submission_no = serializers.IntegerField(min_value=1)


class BulkRegistrationReview(ReviewSerializer):
    items: serializers.ListSerializer = serializers.ListSerializer(
        child=BulkReviewTarget(), allow_empty=False, max_length=20
    )

    def validate_items(self, items):
        if len({item["registration_id"] for item in items}) != len(items):
            raise serializers.ValidationError(
                "A registration may only be reviewed once per batch."
            )
        return items


class BulkReviewResult(StrictSerializer):
    registration_id = serializers.IntegerField()
    code = serializers.IntegerField()
    status = serializers.ChoiceField(choices=REGISTRATION_STATES, allow_null=True)


class ReviewQueueFilters(serializers.Serializer):
    edition = serializers.IntegerField(min_value=1, max_value=2**53 - 1, required=False)
    event = serializers.IntegerField(min_value=1, max_value=2**53 - 1, required=False)
    group = serializers.IntegerField(min_value=1, max_value=2**53 - 1, required=False)
    org = serializers.IntegerField(min_value=1, max_value=2**53 - 1, required=False)
    status = serializers.ChoiceField(choices=REGISTRATION_STATES, required=False)
    q = serializers.CharField(max_length=80, allow_blank=True, required=False)


class ReviewQueueFacetQuery(serializers.Serializer):
    dimension = serializers.ChoiceField(choices=["edition", "event", "group", "org"])
    edition = serializers.IntegerField(min_value=1, max_value=2**53 - 1, required=False)


class ReviewQueueOption(StrictSerializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class ReviewQueueItem(StrictSerializer):
    id = serializers.IntegerField()
    batch_no = serializers.CharField()
    team_code = serializers.CharField(allow_null=True)
    edition_name = serializers.CharField()
    event_name = serializers.CharField()
    group_name = serializers.CharField()
    org_name = serializers.CharField()
    status = serializers.ChoiceField(choices=REGISTRATION_STATES)
    can_review = serializers.BooleanField()
    submission_no = serializers.IntegerField()
    submitted_at = serializers.DateTimeField()


class ApprovalRecord(serializers.Serializer):
    id = serializers.IntegerField()
    submission_no = serializers.IntegerField()
    action = serializers.ChoiceField(
        choices=["approve", "reject", "return", "withdraw", "cancel_review"]
    )
    comment = serializers.CharField(allow_blank=True)
    reviewer_id = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class MemberSummary(serializers.Serializer):
    user_id = serializers.IntegerField()
    real_name = serializers.CharField()
    role = serializers.ChoiceField(choices=["captain", "member"])
    school_level = serializers.CharField(allow_null=True)
    grade = serializers.CharField(allow_null=True)


class ReviewedMember(MemberSummary):
    # 06 §成员字段分级：完整证件号永不出现在响应中，作用域内审核者最多到末四位。
    document_type = serializers.CharField(allow_null=True, required=False)
    document_country = serializers.CharField(allow_null=True, required=False)
    document_last4 = serializers.CharField(allow_null=True, required=False)


class Registration(serializers.Serializer):
    id = serializers.IntegerField()
    batch_no = serializers.CharField()
    edition_id = serializers.IntegerField()
    offering_id = serializers.IntegerField()
    enrollment_kind = serializers.ChoiceField(choices=["individual", "team"])
    team_id = serializers.IntegerField(allow_null=True)
    individual_user_id = serializers.IntegerField(allow_null=True)
    org_id = serializers.IntegerField()
    submitted_by = serializers.IntegerField()
    status = serializers.ChoiceField(choices=REGISTRATION_STATES)
    current_submission_no = serializers.IntegerField(allow_null=True)
    approved_submission_no = serializers.IntegerField(allow_null=True)
    version = serializers.IntegerField()
    selected_school_level = serializers.CharField(allow_null=True)
    coach_user_id = serializers.IntegerField(allow_null=True)
    contact = Contact(required=False)
    form_data = FormData(required=False)
    consents = Consents(required=False)
    members = ReviewedMember(many=True)
    files = serializers.ListField(child=serializers.DictField())
    approval_records = ApprovalRecord(many=True)
    can_edit = serializers.BooleanField()


class SubmittedMember(Member):
    user_id = serializers.IntegerField(allow_null=True)


class Submission(serializers.Serializer):
    submission_no = serializers.IntegerField()
    offering_id = serializers.IntegerField()
    event_name = serializers.CharField(source="offering.event.name")
    group_name = serializers.CharField(source="offering.group.name")
    selected_school_level = serializers.CharField(allow_null=True)
    submitted_at = serializers.DateTimeField()
    cancelled_at = serializers.DateTimeField(allow_null=True)
    members = SubmittedMember(many=True)

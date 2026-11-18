from rest_framework import serializers

from apps.teams.serializers import Member
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


class ApprovalRecord(serializers.Serializer):
    id = serializers.IntegerField()
    submission_no = serializers.IntegerField()
    action = serializers.ChoiceField(
        choices=["approve", "reject", "return", "withdraw", "cancel_review"]
    )
    comment = serializers.CharField(allow_blank=True)
    reviewer_id = serializers.IntegerField()
    created_at = serializers.DateTimeField()


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
    status = serializers.ChoiceField(
        choices=[
            "draft",
            "pending_review",
            "returned",
            "rejected",
            "approved",
            "withdrawn",
        ]
    )
    current_submission_no = serializers.IntegerField(allow_null=True)
    approved_submission_no = serializers.IntegerField(allow_null=True)
    version = serializers.IntegerField()
    selected_school_level = serializers.CharField(allow_null=True)
    coach_user_id = serializers.IntegerField(allow_null=True)
    contact = Contact(required=False)
    form_data = FormData(required=False)
    consents = Consents(required=False)
    members = Member(many=True)
    files = serializers.ListField(child=serializers.DictField())
    approval_records = ApprovalRecord(many=True)
    can_edit = serializers.BooleanField()


class Submission(serializers.Serializer):
    submission_no = serializers.IntegerField()
    selected_school_level = serializers.CharField(allow_null=True)
    submitted_at = serializers.DateTimeField()
    cancelled_at = serializers.DateTimeField(allow_null=True)
    members = Member(many=True)

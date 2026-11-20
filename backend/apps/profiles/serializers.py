from rest_framework import serializers

from core.serializers import StrictSerializer

DOCUMENT_TYPE_CHOICES = ["id_card", "passport"]


class StudentAccountDraft(StrictSerializer):
    real_name = serializers.CharField(max_length=64)
    document_type = serializers.ChoiceField(choices=DOCUMENT_TYPE_CHOICES)
    document_country = serializers.CharField(max_length=2)
    document_number = serializers.CharField(max_length=32)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    student_no = serializers.CharField(max_length=64, required=False, allow_blank=True)


class StudentAccount(StrictSerializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.CharField(allow_null=True)
    status = serializers.CharField()
    must_change_password = serializers.BooleanField()
    initial_password_expires_at = serializers.DateTimeField(allow_null=True)
    document_type = serializers.CharField()
    document_country = serializers.CharField()
    document_last4 = serializers.CharField()
    real_name = serializers.CharField()
    org_id = serializers.IntegerField()
    # 一次性临时密码只出现在创建响应里，绝不与查询接口共用。
    temporary_password = serializers.CharField(required=False)


class StudentPasswordReset(StrictSerializer):
    primary_membership_id = serializers.IntegerField(min_value=1)
    affiliation_version = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=1000)


class StudentPasswordResetResult(StrictSerializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    must_change_password = serializers.BooleanField()
    initial_password_expires_at = serializers.DateTimeField(allow_null=True)
    temporary_password = serializers.CharField()


class IdentityChangeDraft(StrictSerializer):
    user_id = serializers.IntegerField(min_value=1, required=False)
    document_type = serializers.ChoiceField(choices=DOCUMENT_TYPE_CHOICES)
    document_country = serializers.CharField(max_length=2)
    document_number = serializers.CharField(max_length=32)


class IdentityChangeRequest(StrictSerializer):
    id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    status = serializers.ChoiceField(
        choices=["draft", "submitted", "approved", "returned", "rejected", "withdrawn"]
    )
    base_identity_version = serializers.IntegerField()
    new_document_type = serializers.CharField()
    new_document_country = serializers.CharField()
    new_document_last4 = serializers.CharField()
    has_old_document = serializers.BooleanField()
    submitted_by = serializers.IntegerField()
    reviewer_id = serializers.IntegerField(allow_null=True)
    comment = serializers.CharField()
    reviewed_at = serializers.CharField(allow_null=True)
    created_at = serializers.CharField()


class IdentityChangeReview(StrictSerializer):
    action = serializers.ChoiceField(choices=["approve", "return", "reject"])
    comment = serializers.CharField(max_length=2000, allow_blank=True)
    version = serializers.IntegerField(min_value=0)

    def validate(self, attrs):
        if attrs["action"] != "approve" and not attrs["comment"].strip():
            raise serializers.ValidationError({"comment": ["A reason is required."]})
        return attrs

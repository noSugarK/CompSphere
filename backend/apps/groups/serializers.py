from rest_framework import serializers

from core.constants import CONFIGURATION_STATES, SCHOOL_LEVELS
from core.serializers import StrictSerializer


class GroupDraft(StrictSerializer):
    code = serializers.RegexField(r"\A[A-Z0-9][A-Z0-9-]{0,7}\Z", max_length=8)
    name = serializers.CharField(max_length=64)
    school_level = serializers.ChoiceField(choices=SCHOOL_LEVELS, allow_null=True)
    enrollment_type = serializers.ChoiceField(choices=["individual", "team", "both"])
    grade_limits = serializers.ListField(
        child=serializers.CharField(max_length=32), max_length=32
    )

    def to_internal_value(self, data):
        grades = data.get("grade_limits") if isinstance(data, dict) else None
        if isinstance(grades, list) and any(
            not isinstance(grade, str) for grade in grades
        ):
            raise serializers.ValidationError(
                {"grade_limits": ["Grade labels must be strings."]}
            )
        return super().to_internal_value(data)

    def validate_grade_limits(self, values):
        if len(set(values)) != len(values):
            raise serializers.ValidationError("Grade labels must be unique.")
        return values


class ManagedGroup(GroupDraft):
    id = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(choices=CONFIGURATION_STATES)

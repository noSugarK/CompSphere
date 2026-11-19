from rest_framework import serializers

from apps.competitions.serializers import EditionTimeField, normalize_edition_times
from core.constants import CONFIGURATION_STATES
from core.serializers import StrictSerializer


class EventTypeSummary(StrictSerializer):
    code = serializers.CharField(max_length=16)
    name = serializers.CharField(max_length=64)


class EditionEventRules(StrictSerializer):
    name = serializers.CharField(max_length=64)
    min_members = serializers.IntegerField(min_value=1, max_value=2147483647)
    max_members = serializers.IntegerField(min_value=1, max_value=2147483647)
    coach_required = serializers.BooleanField()

    def validate(self, attrs):
        if (
            "min_members" in attrs
            and "max_members" in attrs
            and attrs["min_members"] > attrs["max_members"]
        ):
            raise serializers.ValidationError(
                {"max_members": ["Maximum is smaller than minimum."]}
            )
        return attrs


class EditionEventDraft(EditionEventRules):
    event_code: serializers.CharField = serializers.RegexField(
        r"\A[A-Z0-9][A-Z0-9-]{0,15}\Z", max_length=16
    )


class ManagedEvent(EditionEventDraft):
    id = serializers.IntegerField(min_value=1)
    event_code = serializers.CharField(source="code_id", max_length=16)
    status = serializers.ChoiceField(choices=CONFIGURATION_STATES)


class OfferingDraft(StrictSerializer):
    event_id = serializers.IntegerField(min_value=1)
    group_id = serializers.IntegerField(min_value=1)


class OfferingOverrides(StrictSerializer):
    time_zone = serializers.ChoiceField(choices=["Asia/Shanghai"], required=False)
    enroll_start = EditionTimeField(allow_null=True, required=False)
    enroll_end = EditionTimeField(allow_null=True, required=False)
    quota = serializers.IntegerField(
        min_value=0, max_value=2147483647, allow_null=True, required=False
    )

    def validate(self, attrs):
        return normalize_edition_times(attrs, ("enroll_start", "enroll_end"))


class ManagedOffering(OfferingDraft):
    id = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(choices=CONFIGURATION_STATES)
    enroll_start = serializers.DateTimeField(allow_null=True)
    enroll_end = serializers.DateTimeField(allow_null=True)
    quota = serializers.IntegerField(allow_null=True)
    is_enabled = serializers.SerializerMethodField()

    def get_is_enabled(self, item) -> bool:
        return item.status == item.event.status == item.group.status == "enabled"

from rest_framework import serializers

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


class ManagedOffering(OfferingDraft):
    id = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(choices=CONFIGURATION_STATES)
    is_enabled = serializers.SerializerMethodField()

    def get_is_enabled(self, item) -> bool:
        return item.status == item.event.status == item.group.status == "enabled"

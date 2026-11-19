from datetime import UTC
from zoneinfo import ZoneInfo

from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.serializers import StrictSerializer


class Season(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    status = serializers.ChoiceField(choices=["draft", "active", "archived"])


class SeasonDraft(StrictSerializer):
    code = serializers.RegexField(r"\A[A-Z0-9][A-Z0-9-]{0,31}\Z", max_length=32)
    name = serializers.CharField(max_length=64)
    start_date = serializers.DateField(source="starts_on")
    end_date = serializers.DateField(source="ends_on")

    def validate(self, attrs):
        if attrs["starts_on"] > attrs["ends_on"]:
            raise serializers.ValidationError(
                {"end_date": ["End date precedes start date."]}
            )
        return attrs


class ManagedSeason(Season):
    code = serializers.CharField(max_length=32)
    start_date = serializers.DateField(source="starts_on")
    end_date = serializers.DateField(source="ends_on")
    is_default = serializers.BooleanField()


@extend_schema_field(OpenApiTypes.STR)
class EditionTimeField(serializers.DateTimeField):
    def to_internal_value(self, value):
        if isinstance(value, str) and "T" in value:
            try:
                instant = parse_datetime(value)
            except ValueError:
                instant = None
            if instant is not None:
                return instant
        raise serializers.ValidationError("Provide an ISO date and time.")


def normalize_edition_times(attrs, fields):
    zone = attrs.pop("time_zone", None)
    for field in fields:
        instant = attrs.get(field)
        if instant is None:
            continue
        if is_aware(instant) == (zone is not None):
            raise serializers.ValidationError(
                {field: ["Use an explicit offset or a local time with time_zone."]}
            )
        if zone is not None:
            instant = instant.replace(tzinfo=ZoneInfo(zone), fold=0)
            if instant.utcoffset() != instant.replace(fold=1).utcoffset():
                raise serializers.ValidationError(
                    {field: ["Local time is ambiguous or does not exist."]}
                )
        try:
            attrs[field] = instant.astimezone(UTC)
        except OverflowError as exc:
            raise serializers.ValidationError(
                {field: ["Date and time is out of range."]}
            ) from exc
    return attrs


class EditionDraft(StrictSerializer):
    season_id = serializers.IntegerField(min_value=1)
    edition_no = serializers.IntegerField(min_value=1, max_value=9999)
    year = serializers.IntegerField(min_value=1, max_value=9999)
    name = serializers.CharField(max_length=128)
    venue = serializers.CharField(max_length=255)
    time_zone = serializers.ChoiceField(choices=["Asia/Shanghai"], required=False)
    enroll_start = EditionTimeField()
    enroll_end = EditionTimeField()
    start_date = EditionTimeField()
    end_date = EditionTimeField()

    def validate(self, attrs):
        normalize_edition_times(
            attrs, ("enroll_start", "enroll_end", "start_date", "end_date")
        )
        if (
            not attrs["enroll_start"]
            < attrs["enroll_end"]
            <= attrs["start_date"]
            < attrs["end_date"]
        ):
            raise serializers.ValidationError(
                {"end_date": ["Registration and event dates are out of order."]}
            )
        return attrs


class ManagedEdition(StrictSerializer):
    id = serializers.IntegerField(min_value=1)
    competition_id = serializers.IntegerField(min_value=1)
    season_id = serializers.IntegerField(min_value=1)
    edition_no = serializers.IntegerField(min_value=1)
    year = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=128)
    venue = serializers.CharField(allow_blank=True)
    status = serializers.ChoiceField(choices=["draft", "published", "closed"])
    enroll_start = serializers.DateTimeField()
    enroll_end = serializers.DateTimeField()
    start_date = serializers.DateTimeField()
    end_date = serializers.DateTimeField()


class EditionPublicationChecks(StrictSerializer):
    active_season = serializers.BooleanField()
    title_and_venue = serializers.BooleanField()
    ordered_schedule = serializers.BooleanField()
    open_offering = serializers.BooleanField()
    supported_rules = serializers.BooleanField()


class Offering(serializers.Serializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    event_code = serializers.CharField()
    event_name = serializers.CharField()
    group_id = serializers.IntegerField()
    group_name = serializers.CharField()
    school_level = serializers.CharField(allow_null=True)
    enrollment_type = serializers.ChoiceField(choices=["individual", "team", "both"])
    min_members = serializers.IntegerField()
    max_members = serializers.IntegerField()
    require_coach = serializers.BooleanField()
    enroll_start = serializers.DateTimeField()
    enroll_end = serializers.DateTimeField()
    quota = serializers.IntegerField(allow_null=True)
    required_materials = serializers.ListField(child=serializers.CharField())
    is_enabled = serializers.BooleanField()


class Edition(serializers.Serializer):
    id = serializers.IntegerField()
    competition_id = serializers.IntegerField()
    season_id = serializers.IntegerField()
    name = serializers.CharField()
    status = serializers.ChoiceField(choices=["draft", "published", "closed"])
    approval_mode = serializers.ChoiceField(choices=["single"])
    enroll_start = serializers.DateTimeField()
    enroll_end = serializers.DateTimeField()
    start_date = serializers.DateTimeField()
    end_date = serializers.DateTimeField()
    venue = serializers.CharField(allow_blank=True)
    offerings = Offering(many=True)


class Competition(serializers.Serializer):
    id = serializers.IntegerField()
    public_code = serializers.CharField()
    name = serializers.CharField()
    summary = serializers.CharField(allow_blank=True)
    status = serializers.ChoiceField(choices=["published"])
    editions = Edition(many=True)


class CompetitionDraft(StrictSerializer):
    name = serializers.CharField(max_length=128)
    summary = serializers.CharField(max_length=2000, allow_blank=True)


class ManagedCompetition(StrictSerializer):
    id = serializers.IntegerField(min_value=1)
    public_code = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=128)
    summary = serializers.CharField(allow_blank=True)
    status = serializers.ChoiceField(choices=["draft", "published", "archived"])


class Organization(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    path = serializers.CharField()
    status = serializers.CharField()


class OrganizationMember(serializers.Serializer):
    id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    real_name = serializers.CharField()
    person_type = serializers.CharField()
    school_level = serializers.CharField(allow_null=True)
    grade = serializers.CharField(allow_null=True)

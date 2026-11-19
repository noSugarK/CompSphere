from rest_framework import serializers

from core.serializers import StrictSerializer


class Season(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    status = serializers.ChoiceField(choices=["draft", "active", "archived"])


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

from rest_framework import serializers

from core.serializers import StrictSerializer


class ProposedMember(StrictSerializer):
    user_id = serializers.IntegerField(min_value=1)
    role = serializers.ChoiceField(choices=["captain", "member"])


class TeamProposal(StrictSerializer):
    name = serializers.CharField(max_length=128)
    coach_id = serializers.IntegerField(min_value=1, allow_null=True)
    captain_id = serializers.IntegerField(min_value=1, allow_null=True)
    members = serializers.ListField(child=ProposedMember(), max_length=100)

    def validate(self, attrs):
        ids = [x["user_id"] for x in attrs["members"]]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError({"members": ["Duplicate members."]})
        captains = [x["user_id"] for x in attrs["members"] if x["role"] == "captain"]
        if captains != ([] if attrs["captain_id"] is None else [attrs["captain_id"]]):
            raise serializers.ValidationError(
                {"captain_id": ["Captain must match one member."]}
            )
        return attrs


class TeamRequestCreate(StrictSerializer):
    request_kind = serializers.ChoiceField(choices=["create", "update"])
    org_id = serializers.IntegerField(min_value=1)
    team_code = serializers.RegexField(r"^[A-Z0-9-]{1,32}$")
    event_code = serializers.CharField(max_length=16)
    registration_season_id = serializers.IntegerField(min_value=1, required=False)
    team_id = serializers.IntegerField(min_value=1, required=False)
    base_revision_id = serializers.IntegerField(min_value=1, required=False)
    base_membership_version = serializers.IntegerField(min_value=1, required=False)
    proposal = TeamProposal()

    def validate(self, attrs):
        revision_fields = {"team_id", "base_revision_id", "base_membership_version"}
        if attrs["request_kind"] == "create":
            if "registration_season_id" not in attrs or revision_fields & attrs.keys():
                raise serializers.ValidationError(
                    "Create requires season and no existing team version."
                )
        elif not revision_fields <= attrs.keys() or "registration_season_id" in attrs:
            raise serializers.ValidationError(
                "Update requires team and current version only."
            )
        return attrs


class SeasonRequestCreate(StrictSerializer):
    team_id = serializers.IntegerField(min_value=1)
    season_id = serializers.IntegerField(min_value=1)


class SeasonReview(StrictSerializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    comment = serializers.CharField(max_length=2000)


class Member(serializers.Serializer):
    user_id = serializers.IntegerField()
    real_name = serializers.CharField()
    role = serializers.ChoiceField(choices=["captain", "member"])
    school_level = serializers.CharField(allow_null=True)
    grade = serializers.CharField(allow_null=True)


class SeasonRegistration(serializers.Serializer):
    id = serializers.IntegerField()
    team_id = serializers.IntegerField()
    season_id = serializers.IntegerField()
    status = serializers.ChoiceField(
        choices=["draft", "submitted", "approved", "rejected", "withdrawn", "revoked"]
    )
    submitted_by = serializers.IntegerField()
    reviewer_id = serializers.IntegerField(allow_null=True)
    comment = serializers.CharField(allow_blank=True)


class Team(serializers.Serializer):
    id = serializers.IntegerField()
    team_code = serializers.CharField()
    event_code = serializers.CharField()
    name = serializers.CharField()
    org_id = serializers.IntegerField()
    coach_id = serializers.IntegerField(allow_null=True)
    captain_id = serializers.IntegerField(allow_null=True)
    approved_revision_id = serializers.IntegerField(allow_null=True)
    membership_version = serializers.IntegerField()
    status = serializers.ChoiceField(choices=["active", "disbanded"])
    members = Member(many=True, required=False)
    season_registrations = SeasonRegistration(many=True)


class TeamChangeRequest(serializers.Serializer):
    id = serializers.IntegerField()
    request_kind = serializers.ChoiceField(choices=["create", "update"])
    team_id = serializers.IntegerField(allow_null=True)
    org_id = serializers.IntegerField()
    status = serializers.ChoiceField(
        choices=["draft", "submitted", "approved", "returned", "rejected", "withdrawn"]
    )
    submitted_by = serializers.IntegerField()
    base_revision_id = serializers.IntegerField(allow_null=True)
    base_membership_version = serializers.IntegerField()
    registration_season_id = serializers.IntegerField(allow_null=True)
    proposal = TeamProposal()
    comment = serializers.CharField(allow_blank=True)

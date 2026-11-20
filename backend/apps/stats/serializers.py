from rest_framework import serializers

from core.serializers import StrictSerializer


class OfferingCounts(StrictSerializer):
    event_name = serializers.CharField()
    group_name = serializers.CharField()
    submitted = serializers.IntegerField()
    approved = serializers.IntegerField()


class Dashboard(StrictSerializer):
    registrations = serializers.IntegerField()
    approved = serializers.IntegerField()
    approval_rate = serializers.FloatField(allow_null=True)
    awarded = serializers.IntegerField()
    by_offering = OfferingCounts(many=True)
    users = serializers.IntegerField(required=False)
    organizations = serializers.IntegerField(required=False)
    competitions = serializers.IntegerField(required=False)
    editions = serializers.IntegerField(required=False)

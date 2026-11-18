from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import inline_serializer
from rest_framework import serializers

from core.serializers import StrictSerializer


class StrictAutoSchema(AutoSchema):
    def _map_serializer(self, serializer, direction, bypass_extensions=False):
        result = super()._map_serializer(serializer, direction, bypass_extensions)
        if isinstance(serializer, StrictSerializer) and result.get("type") == "object":
            result["additionalProperties"] = False
        return result

    def _map_serializer_field(self, field, direction, bypass_extensions=False):
        result = super()._map_serializer_field(field, direction, bypass_extensions)
        if (
            isinstance(field, serializers.IntegerField)
            and result
            and result.get("type") == "integer"
        ):
            result["maximum"] = min(result.get("maximum", 2**53 - 1), 2**53 - 1)
            result["minimum"] = max(result.get("minimum", -(2**53 - 1)), -(2**53 - 1))
        return result


def envelope(name, serializer, many=False, nullable=False):
    instance = (
        serializer(many=many, allow_null=nullable)
        if isinstance(serializer, type)
        else serializer
    )
    return inline_serializer(
        name=name,
        fields={
            "code": serializers.IntegerField(),
            "message": serializers.CharField(),
            "data": instance,
            "request_id": serializers.UUIDField(),
        },
    )


def listing(name, serializer):
    return envelope(
        name + "Response",
        inline_serializer(
            name=name + "Page",
            fields={
                "items": serializer(many=True),
                "page": serializers.IntegerField(min_value=1),
                "page_size": serializers.IntegerField(min_value=1, max_value=100),
                "total": serializers.IntegerField(min_value=0),
            },
        ),
    )

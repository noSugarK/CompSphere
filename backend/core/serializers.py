from rest_framework import serializers


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError(
                {"non_field_errors": ["Expected an object."]}
            )
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError(
                {"non_field_errors": ["Unknown fields are not accepted."]}
            )
        for name, value in data.items():
            field = self.fields[name]
            if value is None and field.allow_null:
                continue
            if isinstance(field, serializers.IntegerField) and type(value) is not int:
                raise serializers.ValidationError({name: ["Expected an integer."]})
            if (
                isinstance(field, serializers.IntegerField)
                and type(value) is int
                and not -(2**53 - 1) <= value <= 2**53 - 1
            ):
                raise serializers.ValidationError(
                    {name: ["Integer is outside the supported JSON range."]}
                )
            if isinstance(field, serializers.BooleanField) and type(value) is not bool:
                raise serializers.ValidationError({name: ["Expected a boolean."]})
            if isinstance(
                field, (serializers.CharField, serializers.ChoiceField)
            ) and not isinstance(value, str):
                raise serializers.ValidationError({name: ["Expected a string."]})
        return super().to_internal_value(data)


class EmptySerializer(StrictSerializer):
    pass


class VersionSerializer(StrictSerializer):
    version = serializers.IntegerField(min_value=1)


class ReviewSerializer(StrictSerializer):
    action = serializers.ChoiceField(choices=["approve", "reject", "return"])
    comment = serializers.CharField(max_length=2000, allow_blank=True)

    def validate(self, attrs):
        if attrs["action"] != "approve" and not attrs["comment"].strip():
            raise serializers.ValidationError({"comment": ["A reason is required."]})
        return attrs

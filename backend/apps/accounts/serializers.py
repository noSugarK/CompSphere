from rest_framework import serializers

from core.serializers import StrictSerializer


class LoginSerializer(StrictSerializer):
    login_type = serializers.ChoiceField(choices=["email", "document"])
    email = serializers.EmailField(max_length=255, required=False)
    password = serializers.CharField(
        max_length=256, trim_whitespace=False, write_only=True
    )
    document_type = serializers.ChoiceField(
        choices=["id_card", "passport"], required=False
    )
    document_country = serializers.CharField(min_length=2, max_length=2, required=False)
    document_number = serializers.CharField(max_length=32, required=False)

    def validate(self, attrs):
        expected = (
            {"login_type", "password", "email"}
            if attrs["login_type"] == "email"
            else {
                "login_type",
                "password",
                "document_type",
                "document_country",
                "document_number",
            }
        )
        if set(attrs) != expected:
            raise serializers.ValidationError("Login fields do not match login_type.")
        return attrs


class PreferencesSerializer(StrictSerializer):
    locale = serializers.ChoiceField(choices=["zh-CN", "en-US"], required=False)
    theme = serializers.ChoiceField(choices=["light", "dark", "system"], required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one preference is required.")
        return attrs


class PasswordChangeSerializer(StrictSerializer):
    old_password = serializers.CharField(
        max_length=256, trim_whitespace=False, write_only=True
    )
    new_password = serializers.CharField(
        min_length=12, max_length=256, trim_whitespace=False, write_only=True
    )


class VerificationRequestSerializer(StrictSerializer):
    email = serializers.EmailField(max_length=255)
    purpose = serializers.ChoiceField(choices=["register", "reset_password"])

    def validate_email(self, value):
        return value.strip().lower()


class RegisterSerializer(StrictSerializer):
    email = serializers.EmailField(max_length=255)
    password = serializers.CharField(
        min_length=12, max_length=256, trim_whitespace=False, write_only=True
    )
    verification_code = serializers.RegexField(
        r"\A[0-9]{6}\Z", min_length=6, max_length=6, write_only=True
    )
    real_name = serializers.CharField(max_length=64)

    def validate_email(self, value):
        return value.strip().lower()


class PasswordResetSerializer(StrictSerializer):
    email = serializers.EmailField(max_length=255)
    verification_code = serializers.RegexField(
        r"\A[0-9]{6}\Z", min_length=6, max_length=6, write_only=True
    )
    new_password = serializers.CharField(
        min_length=12, max_length=256, trim_whitespace=False, write_only=True
    )

    def validate_email(self, value):
        return value.strip().lower()

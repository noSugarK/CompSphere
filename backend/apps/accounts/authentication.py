from typing import cast

from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

from apps.accounts.models import User


class VersionedJWTScheme(SimpleJWTScheme):
    target_class = "apps.accounts.authentication.VersionedJWTAuthentication"


class VersionedJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = cast(User, super().get_user(validated_token))
        if (
            validated_token.get("token_version") != user.token_version
            or user.is_deleted
            or not user.is_active
            or BlacklistedToken.objects.filter(
                token__jti=validated_token["jti"]
            ).exists()
        ):
            raise AuthenticationFailed("Invalid session")
        return user

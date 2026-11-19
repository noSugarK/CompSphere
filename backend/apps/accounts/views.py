from django.conf import settings
from django.db import transaction
from django.middleware.csrf import get_token
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts import services, verification
from apps.accounts.serializers import (
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetSerializer,
    PreferencesSerializer,
    RegisterSerializer,
    VerificationRequestSerializer,
)
from apps.rbac.services import grants
from core.api import BaseView, success, validated
from core.network import client_ip
from core.schema import envelope
from core.serializers import EmptySerializer


class RegisteredAccount(serializers.Serializer):
    id = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(choices=["active"])


def accepted_verification(request):
    response = success(request, status=202)
    response.data["message"] = (
        "If eligible, a verification code will be sent. Please check your inbox."
        if request.headers.get("Accept-Language", "").startswith("en")
        else "如符合条件，验证码将发送，请检查收件箱"
    )
    return response


class VerificationRequestView(BaseView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=VerificationRequestSerializer,
        responses={
            202: envelope(
                "VerificationAcceptedResponse", serializers.JSONField(allow_null=True)
            )
        },
    )
    def post(self, request):
        data = validated(VerificationRequestSerializer, request)
        locale = (
            "en-US"
            if request.headers.get("Accept-Language", "").startswith("en")
            else "zh-CN"
        )
        verification.request_verification(
            data["email"], data["purpose"], client_ip(request), locale
        )
        return accepted_verification(request)


class RegisterView(BaseView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=RegisterSerializer,
        responses={201: envelope("RegisterResponse", RegisteredAccount)},
    )
    def post(self, request):
        return success(
            request,
            verification.register_account(**validated(RegisterSerializer, request)),
            status=201,
        )


class PasswordResetView(BaseView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=PasswordResetSerializer,
        responses={
            202: envelope(
                "PasswordResetResponse", serializers.JSONField(allow_null=True)
            )
        },
    )
    def post(self, request):
        verification.reset_password(**validated(PasswordResetSerializer, request))
        response = success(request, status=202)
        response.data["message"] = (
            "Password reset request accepted. Try signing in with the new password."
            if request.headers.get("Accept-Language", "").startswith("en")
            else "密码重置请求已受理，请尝试使用新密码登录。"
        )
        return response


class TokenPair(serializers.Serializer):
    access = serializers.CharField()
    expires_in = serializers.IntegerField()


class UserInfo(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField(allow_null=True)
    must_change_password = serializers.BooleanField()


class ProfileInfo(serializers.Serializer):
    real_name = serializers.CharField()
    person_type = serializers.CharField()
    school_level = serializers.CharField(allow_null=True)
    grade = serializers.CharField(allow_null=True)


class GrantInfo(serializers.Serializer):
    role = serializers.CharField()
    scope_type = serializers.ChoiceField(
        choices=["global", "org", "competition", "edition"]
    )
    scope_id = serializers.IntegerField(allow_null=True)
    permissions = serializers.ListField(child=serializers.CharField())


class Me(serializers.Serializer):
    user = UserInfo()
    profile = ProfileInfo(allow_null=True)
    grants = GrantInfo(many=True)
    locale = serializers.ChoiceField(choices=["zh-CN", "en-US"])
    theme = serializers.ChoiceField(choices=["light", "dark", "system"])


def attach_refresh(response, raw):
    response.set_cookie(
        "refresh",
        raw,
        max_age=7 * 86400,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite="Strict",
        path="/api/v1/auth",
    )
    return response


class LoginView(BaseView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=LoginSerializer, responses=envelope("LoginResponse", TokenPair)
    )
    def post(self, request):
        data = validated(LoginSerializer, request)
        user = services.login_user(request, data)
        body, refresh = services.issue_tokens(user)
        return attach_refresh(success(request, body), refresh)


class CsrfView(BaseView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        responses=envelope(
            "CsrfResponse",
            inline_serializer(
                name="Csrf", fields={"csrf_token": serializers.CharField()}
            ),
        )
    )
    def get(self, request):
        return success(request, {"csrf_token": get_token(request._request)})


class RefreshView(BaseView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=EmptySerializer, responses=envelope("RefreshResponse", TokenPair)
    )
    def post(self, request):
        validated(EmptySerializer, request)
        services.check_cookie_request(request)
        data, refresh = services.rotate_refresh(request.COOKIES.get("refresh", ""))
        return attach_refresh(success(request, data), refresh)


class LogoutView(BaseView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=EmptySerializer,
        responses=envelope("LogoutResponse", serializers.JSONField(allow_null=True)),
    )
    def post(self, request):
        validated(EmptySerializer, request)
        services.check_cookie_request(request)
        with transaction.atomic():
            try:
                raw = request.COOKIES.get("refresh")
                if raw:
                    RefreshToken(raw).blacklist()
            except TokenError:
                pass
            services.revoke_access(request.user, request.auth)
        response = success(request)
        response.delete_cookie("refresh", path="/api/v1/auth", samesite="Strict")
        return response


class MeView(BaseView):
    @extend_schema(responses=envelope("MeResponse", Me))
    def get(self, request):
        user = request.user
        profile = getattr(user, "profile", None)
        return success(
            request,
            {
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "must_change_password": user.must_change_password,
                },
                "profile": (
                    {
                        "real_name": profile.real_name,
                        "person_type": profile.person_type,
                        "school_level": profile.school_level,
                        "grade": profile.grade,
                    }
                    if profile
                    else None
                ),
                "grants": grants(user),
                "locale": user.locale,
                "theme": user.theme,
            },
        )


class PreferencesView(BaseView):
    @extend_schema(
        request=PreferencesSerializer,
        responses=envelope(
            "PreferencesResponse",
            inline_serializer(
                name="Preferences",
                fields={
                    "locale": serializers.ChoiceField(choices=["zh-CN", "en-US"]),
                    "theme": serializers.ChoiceField(
                        choices=["light", "dark", "system"]
                    ),
                },
            ),
        ),
    )
    def patch(self, request):
        data = validated(PreferencesSerializer, request)
        for key, value in data.items():
            setattr(request.user, key, value)
        request.user.save(update_fields=[*data, "updated_at"])
        return success(
            request, {"locale": request.user.locale, "theme": request.user.theme}
        )


class PasswordChangeView(BaseView):
    @extend_schema(
        request=PasswordChangeSerializer,
        responses=envelope("PasswordChangeResponse", TokenPair),
    )
    def post(self, request):
        data = validated(PasswordChangeSerializer, request)
        body, refresh = services.change_password(request.user, **data)
        return attach_refresh(success(request, body), refresh)

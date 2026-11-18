import hashlib
import hmac
from datetime import UTC, datetime

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse
from rest_framework.authentication import CSRFCheck
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.audit.services import audit
from apps.profiles.models import Profile
from core.exceptions import BusinessError

_dummy_password = make_password("never-a-user-credential")


def check_cookie_request(request):
    if request.headers.get("Origin") != settings.SITE_BASE_URL:
        raise BusinessError(40301, "Origin is not allowed", 403)

    def callback(req):
        return HttpResponse()

    check = CSRFCheck(callback)
    check.process_request(request._request)
    reason = check.process_view(request._request, callback, (), {})
    if reason:
        raise BusinessError(40301, "CSRF verification failed", 403)


def login_user(request, data):
    identity = data.get("email", data.get("document_number", "")).strip().lower()
    key = (
        "login:"
        + hashlib.sha256(
            (identity + "|" + request.META.get("REMOTE_ADDR", "")).encode()
        ).hexdigest()
    )
    cache.add(key, 0, timeout=60)
    if cache.incr(key) > 10:
        raise BusinessError(42901, "Too many attempts", 429)
    user = None
    if data["login_type"] == "email":
        user = User.objects.filter(
            email__iexact=data["email"], email_verified_at__isnull=False
        ).first()
    else:
        number = data["document_number"].strip().upper()
        digest = hmac.new(
            settings.DOC_HASH_PEPPER.encode(),
            f"{data['document_type']}|{data['document_country'].upper()}|{number}".encode(),
            hashlib.sha256,
        ).hexdigest()
        profile = (
            Profile.objects.filter(document_hash=digest, is_deleted=False)
            .select_related("user")
            .first()
        )
        user = profile.user if profile else None
    password_valid = check_password(
        data["password"], user.password if user else _dummy_password
    )
    if not user or not password_valid or not user.is_active:
        raise BusinessError(40105, "Invalid credentials", 401)
    from django.utils import timezone

    if (
        user.must_change_password
        and user.initial_password_expires_at
        and user.initial_password_expires_at <= timezone.now()
    ):
        raise BusinessError(40105, "Invalid credentials", 401)
    audit(user, "auth.login", "user", user.id)
    return user


def issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    refresh["token_version"] = user.token_version
    return {"access": str(refresh.access_token), "expires_in": 1800}, str(refresh)


@transaction.atomic
def rotate_refresh(raw):
    try:
        old = RefreshToken(raw)
        outstanding = OutstandingToken.objects.select_for_update().get(jti=old["jti"])
        if BlacklistedToken.objects.filter(token=outstanding).exists():
            raise ValueError
        user = User.objects.select_for_update().get(pk=old["user_id"])
        if not user.is_active or old.get("token_version") != user.token_version:
            raise ValueError
        old.blacklist()
        return issue_tokens(user)
    except Exception as exc:
        from rest_framework_simplejwt.exceptions import TokenError

        if isinstance(
            exc,
            (
                TokenError,
                User.DoesNotExist,
                OutstandingToken.DoesNotExist,
                ValueError,
                KeyError,
            ),
        ):
            raise BusinessError(40101, "Invalid session", 401) from exc
        raise


def revoke_access(user, token):
    if not token:
        return
    outstanding, _ = OutstandingToken.objects.get_or_create(
        jti=token["jti"],
        defaults={
            "user": user,
            "token": "",
            "expires_at": datetime.fromtimestamp(token["exp"], UTC),
        },
    )
    BlacklistedToken.objects.get_or_create(token=outstanding)


@transaction.atomic
def change_password(user, old_password, new_password):
    user = User.objects.select_for_update().get(pk=user.pk)
    if not user.check_password(old_password):
        raise BusinessError(40105, "Invalid credentials", 401)
    from django.core.exceptions import ValidationError as DjangoValidationError
    from rest_framework.exceptions import ValidationError

    try:
        validate_password(new_password, user)
    except DjangoValidationError as exc:
        raise ValidationError(
            {"new_password": ["Password does not meet the security requirements."]}
        ) from exc
    user.set_password(new_password)
    user.must_change_password = False
    user.token_version += 1
    user.save(
        update_fields=[
            "password",
            "must_change_password",
            "token_version",
            "updated_at",
        ]
    )
    audit(user, "account.password_changed", "user", user.id)
    return issue_tokens(user)

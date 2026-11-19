"""Verification acceptance/consumption; SMTP runs only in the outbox worker."""

import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import EmailMessage
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User, VerificationCode
from apps.audit.services import audit
from core.crypto import decrypt, encrypt
from core.exceptions import BusinessError

PURPOSES = ("register", "reset_password")


class VerificationRateLimit(BusinessError):
    def __init__(self, seconds):
        self.wait = seconds
        super().__init__(42901, "Too many requests; please try again later", 429)


def _opaque_key(value):
    return hmac.new(
        settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256
    ).hexdigest()


def _hash_code(email, purpose, code):
    salt = secrets.token_hex(16)
    digest = _opaque_key(f"verification|{salt}|{email}|{purpose}|{code}")
    return f"hmac_sha256${salt}${digest}"


def _code_matches(item, code):
    try:
        algorithm, salt, expected = item.code_hash.split("$")
    except ValueError:
        return False
    if algorithm != "hmac_sha256":
        return False
    actual = _opaque_key(f"verification|{salt}|{item.target}|{item.purpose}|{code}")
    return hmac.compare_digest(actual, expected)


def _limit_acceptance(email, purpose, client_ip):
    interval = settings.CODE_RESEND_INTERVAL_SECONDS
    # Shared-cache atomics are conservative: failed DB acceptance still consumes
    # rate budget, so outages cannot be used to bypass limits or spam retries.
    try:
        ip_key = "verification:ip:" + _opaque_key(client_ip)
        cache.add(ip_key, 0, timeout=3600)
        count = cache.incr(ip_key)
        if count > settings.CODE_IP_HOURLY_LIMIT:
            raise VerificationRateLimit(3600)
        email_key = "verification:email:" + _opaque_key(f"{email}|{purpose}")
        email_allowed = cache.add(email_key, True, timeout=interval)
    except VerificationRateLimit:
        raise
    except Exception as exc:
        raise BusinessError(
            50301, "Verification requests are temporarily unavailable", 503
        ) from exc
    if not email_allowed:
        raise VerificationRateLimit(interval)


def request_verification(email, purpose, client_ip, locale):
    """Do not query User here: accepted response is independent of existence."""
    from apps.notifications.services import queue_verification

    _limit_acceptance(email, purpose, client_ip or "unknown")
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = timezone.now()
    try:
        with transaction.atomic():
            VerificationCode.objects.filter(
                channel="email", target=email, purpose=purpose, consumed_at__isnull=True
            ).update(consumed_at=now, delivery_secret_enc=None)
            item = VerificationCode.objects.create(
                channel="email",
                target=email,
                purpose=purpose,
                code_hash=_hash_code(email, purpose, code),
                delivery_secret_enc=encrypt(code),
                expires_at=now + timedelta(seconds=settings.CODE_TTL_SECONDS),
                client_ip=client_ip,
            )
            queue_verification(item.id, locale)
    except DatabaseError as exc:
        raise BusinessError(
            50301, "Verification requests are temporarily unavailable", 503
        ) from exc


def _password_policy(password, user=None, field="password"):
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise ValidationError(
            {field: ["Password does not meet the security requirements."]}
        ) from exc


def _lock_and_validate(email, purpose, code):
    item = (
        VerificationCode.objects.select_for_update()
        .filter(channel="email", target=email, purpose=purpose)
        .order_by("-id")
        .first()
    )
    now = timezone.now()
    if item is None:
        return None
    if (
        item.consumed_at is not None
        or item.expires_at <= now
        or item.attempts >= min(settings.CODE_MAX_ATTEMPTS, 5)
    ):
        if item.delivery_secret_enc is not None:
            item.delivery_secret_enc = None
            item.save(update_fields=["delivery_secret_enc"])
        return None
    if not _code_matches(item, code):
        item.attempts += 1
        if item.attempts >= min(settings.CODE_MAX_ATTEMPTS, 5):
            item.consumed_at = now
            item.delivery_secret_enc = None
        item.save(update_fields=["attempts", "consumed_at", "delivery_secret_enc"])
        return None
    return item


def _consume(item):
    item.consumed_at = timezone.now()
    item.delivery_secret_enc = None
    item.save(update_fields=["consumed_at", "delivery_secret_enc"])


def register_account(email, password, verification_code, real_name):
    """Raise invalid-code only after the failed-attempt transaction commits."""
    from apps.profiles.services import create_participant_profile
    from apps.rbac.services import grant_participant

    _password_policy(password, User(email=email))
    result = None
    try:
        with transaction.atomic():
            item = _lock_and_validate(email, "register", verification_code)
            if item is not None:
                if User.objects.filter(email__iexact=email).exists():
                    _consume(item)
                else:
                    try:
                        with transaction.atomic():
                            user = User.objects.create_user(
                                email=email,
                                password=password,
                                status="active",
                                email_verified_at=timezone.now(),
                            )
                            create_participant_profile(user, real_name)
                            grant_participant(user)
                    except IntegrityError:
                        _consume(item)
                    else:
                        _consume(item)
                        audit(user, "auth.registered", "user", user.id)
                        result = {"id": user.id, "status": "active"}
    except DatabaseError as exc:
        raise BusinessError(
            50301, "Registration is temporarily unavailable", 503
        ) from exc
    if result is None:
        raise BusinessError(40102, "Invalid or expired verification code", 401)
    return result


def reset_password(email, verification_code, new_password):
    _password_policy(new_password, field="new_password")
    verified = False
    try:
        with transaction.atomic():
            item = _lock_and_validate(email, "reset_password", verification_code)
            if item is not None:
                user = (
                    User.objects.select_for_update()
                    .filter(
                        email__iexact=email,
                        email_verified_at__isnull=False,
                        status="active",
                        is_deleted=False,
                    )
                    .first()
                )
                if user is not None:
                    _password_policy(new_password, user, field="new_password")
                    user.set_password(new_password)
                    user.must_change_password = False
                    user.initial_password_expires_at = None
                    user.token_version += 1
                    user.save(
                        update_fields=[
                            "password",
                            "must_change_password",
                            "initial_password_expires_at",
                            "token_version",
                            "updated_at",
                        ]
                    )
                    audit(user, "account.password_reset", "user", user.id)
                _consume(item)
                verified = True
    except DatabaseError as exc:
        raise BusinessError(
            50301, "Password reset is temporarily unavailable", 503
        ) from exc
    if not verified:
        raise BusinessError(40102, "Invalid or expired verification code", 401)


@transaction.atomic
def prepare_verification_email(code_id: int, locale: str) -> EmailMessage | None:
    item = VerificationCode.objects.select_for_update().filter(pk=code_id).first()
    if item is None:
        return None
    eligible = (
        item.consumed_at is None
        and item.expires_at > timezone.now()
        and item.delivery_secret_enc is not None
        and item.attempts < min(settings.CODE_MAX_ATTEMPTS, 5)
    )
    if eligible:
        occupied = User.objects.filter(email__iexact=item.target)
        eligible = (
            not occupied.exists()
            if item.purpose == "register"
            else occupied.filter(
                email_verified_at__isnull=False, status="active", is_deleted=False
            ).exists()
            if item.purpose == "reset_password"
            else False
        )
    if not eligible:
        item.delivery_secret_enc = None
        item.save(update_fields=["delivery_secret_enc"])
        return None
    code = decrypt(item.delivery_secret_enc)
    if (
        not isinstance(code, str)
        or len(code) != 6
        or not code.isascii()
        or not code.isdecimal()
        or not _code_matches(item, code)
    ):
        raise ValueError("Invalid verification delivery payload")
    minutes = max(1, settings.CODE_TTL_SECONDS // 60)
    if locale == "en-US":
        subject = "CompSphere email verification"
        body = f"Your CompSphere verification code is {code}. It expires in {minutes} minutes. If you did not request this code, ignore this email."
    else:
        subject = "竞云邮箱验证码"
        body = f"你的竞云验证码为 {code}，{minutes} 分钟内有效。如非本人操作，请忽略此邮件。"
    return EmailMessage(
        subject=subject,
        body=body,
        to=[item.target],
        headers={
            "Message-ID": f"<compsphere-verification-{item.pk}@compsphere.invalid>"
        },
    )


def complete_delivery(code_id: int) -> None:
    VerificationCode.objects.filter(pk=code_id).update(delivery_secret_enc=None)


def cleanup_expired_verifications() -> int:
    return (
        VerificationCode.objects.filter(delivery_secret_enc__isnull=False)
        .filter(
            Q(expires_at__lte=timezone.now())
            | Q(consumed_at__isnull=False)
            | Q(attempts__gte=min(settings.CODE_MAX_ATTEMPTS, 5))
        )
        .update(delivery_secret_enc=None)
    )

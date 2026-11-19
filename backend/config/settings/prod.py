from ipaddress import ip_network

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import env

for proxy in TRUSTED_PROXY_IPS:  # noqa: F405
    try:
        network = ip_network(proxy)
        if network.prefixlen == 0:
            raise ValueError("An unrestricted proxy network is unsafe")
    except ValueError as exc:
        raise ImproperlyConfigured(
            "TRUSTED_PROXY_IPS must contain restricted IP/CIDR values"
        ) from exc

for variable in ("SECRET_KEY", "JWT_SIGNING_KEY", "DOC_HASH_PEPPER"):
    value = env(variable, default="")
    if len(value) < 32 or value.lower().startswith(("change-me", "example")):
        raise ImproperlyConfigured(
            f"{variable} must be explicitly configured with at least 32 characters."
        )
try:
    Fernet(env("FIELD_ENCRYPTION_KEY").encode())
except (ValueError, TypeError) as exc:
    raise ImproperlyConfigured(
        "FIELD_ENCRYPTION_KEY must be a valid Fernet key."
    ) from exc

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000

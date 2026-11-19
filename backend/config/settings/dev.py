import json
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

# Development-only persisted keys: never regenerate encryption keys for an existing DB.
directory = Path(__file__).resolve().parents[2]
key_file = directory / ".development-secrets.json"
if not key_file.exists():
    key_file.write_text(
        json.dumps(
            {
                "SECRET_KEY": secrets.token_urlsafe(48),
                "FIELD_ENCRYPTION_KEY": Fernet.generate_key().decode(),
                "DOC_HASH_PEPPER": secrets.token_urlsafe(48),
            }
        )
    )
for key, value in json.loads(key_file.read_text()).items():
    os.environ.setdefault(key, value)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{directory / 'development.sqlite3'}")
from .base import *  # noqa: E402,F403

REFRESH_COOKIE_SECURE = False
IS_DEVELOPMENT = True
CSRF_COOKIE_SECURE = False
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

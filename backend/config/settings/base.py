from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]
env = environ.Env()
SECRET_KEY = env("SECRET_KEY")
DEBUG = False
IS_DEVELOPMENT = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
SITE_BASE_URL = env("SITE_BASE_URL", default="http://localhost:5173").rstrip("/")
CSRF_TRUSTED_ORIGINS = [SITE_BASE_URL]
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "django_celery_beat",
    "apps.accounts",
    "apps.profiles",
    "apps.orgs",
    "apps.rbac",
    "apps.teams",
    "apps.competitions",
    "apps.events",
    "apps.groups",
    "apps.registrations",
    "apps.audit",
    "apps.notifications",
    "core",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.RequestLogMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.locale.LocaleMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATABASES = {"default": env.db("DATABASE_URL")}
LANGUAGE_CODE = "zh-hans"
LANGUAGES = [("zh-hans", "简体中文"), ("en-us", "English")]
TIME_ZONE = "UTC"
USE_TZ = True
APPEND_SLASH = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher"]
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
]
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.VersionedJWTAuthentication"
    ],
    "DEFAULT_PERMISSION_CLASSES": ["apps.rbac.services.ScopedRolePermission"],
    "DEFAULT_SCHEMA_CLASS": "core.schema.StrictAutoSchema",
    "EXCEPTION_HANDLER": "core.exceptions.exception_handler",
    "DEFAULT_PARSER_CLASSES": ["core.parsers.StrictJSONParser"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "SIGNING_KEY": env("JWT_SIGNING_KEY", default=SECRET_KEY),
    "UPDATE_LAST_LOGIN": False,
}
SPECTACULAR_SETTINGS = {
    "TITLE": "CompSphere API",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "ReviewActionEnum": ["approve", "reject", "return"],
        "LicenseActionEnum": ["approve", "reject"],
        "RecordedActionEnum": [
            "approve",
            "reject",
            "return",
            "withdraw",
            "cancel_review",
        ],
    },
}
REFRESH_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_PROXY_SSL_HEADER = None
DATA_UPLOAD_MAX_MEMORY_SIZE = 1_048_576
FILE_UPLOAD_MAX_MEMORY_SIZE = 1_048_576
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY")
DOC_HASH_PEPPER = env("DOC_HASH_PEPPER")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://127.0.0.1:6379/0"),
    }
}
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379/2")
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

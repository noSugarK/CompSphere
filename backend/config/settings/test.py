import environ

from .dev import *  # noqa: F403

env = environ.Env()

DATABASES = (
    {"default": env.db("TEST_DATABASE_URL")}
    if env("TEST_DATABASE_URL", default="")
    else {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
)  # noqa: F405
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SITE_BASE_URL = "http://testserver"
CSRF_TRUSTED_ORIGINS = ["http://testserver"]

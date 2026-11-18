import json

from cryptography.fernet import Fernet
from django.conf import settings


def encrypt(value):
    return Fernet(settings.FIELD_ENCRYPTION_KEY.encode()).encrypt(
        json.dumps(value, ensure_ascii=False).encode()
    )


def decrypt(value):
    return json.loads(
        Fernet(settings.FIELD_ENCRYPTION_KEY.encode()).decrypt(bytes(value))
    )

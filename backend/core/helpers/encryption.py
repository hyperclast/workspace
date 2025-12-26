from cryptography.fernet import Fernet
from django.conf import settings


def encrypt(payload):
    return Fernet(settings.WS_ENCRYPTION_KEY).encrypt(bytes(payload, "utf-8")).decode("utf-8")


def decrypt(payload):
    return Fernet(settings.WS_ENCRYPTION_KEY).decrypt(bytes(payload, "utf-8")).decode("utf-8")

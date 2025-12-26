from typing import Optional

from cryptography.fernet import InvalidToken
from django.db import models
from django.utils.translation import gettext as _

from .helpers import decrypt, encrypt, generate_external_id


class UniqueIDTextField(models.TextField):
    """Model field that generates a random, unique string ID."""

    description = _("Randomly generated unique string ID")

    def __init__(self, length: Optional[int] = 10, *args, **kwargs):
        self.length = length
        kwargs["unique"] = True
        kwargs["editable"] = False

        # Do not use instance method as default to prevent this error:
        # https://code.djangoproject.com/ticket/32689
        kwargs["default"] = kwargs.pop("default", generate_external_id)

        super().__init__(*args, **kwargs)

    def get_default(self) -> str:
        if callable(self.default):
            return self.default(self.length)
        return super().get_default()


class EncryptedTextField(models.TextField):
    """Field for storing and retrieving encrypted text."""

    description = _("TextField that transparently encrypts/decrypts input text")

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value

        try:
            return decrypt(value)

        except InvalidToken:
            return value

    def to_python(self, value):
        return value

    def get_prep_value(self, value):
        if value is None:
            return value

        return encrypt(value)

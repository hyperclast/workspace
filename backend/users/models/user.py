from django.contrib.auth.models import AbstractUser
from django.db import models

from core.fields import UniqueIDTextField


class User(AbstractUser):
    """
    Authentication user model. Only contains auth-related fields.
    Custom user attributes belong on Profile model (user.profile.*).
    """

    external_id = UniqueIDTextField()
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.email

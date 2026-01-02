from django.contrib.auth.models import AbstractUser
from django.db import models

from core.fields import UniqueIDTextField


class User(AbstractUser):
    external_id = UniqueIDTextField()
    email = models.EmailField(unique=True)
    last_active = models.DateTimeField(null=True, blank=True)
    receive_product_updates = models.BooleanField(default=True)

    def __str__(self):
        return self.email

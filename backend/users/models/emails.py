from django.db import models
from django_extensions.db.models import TimeStampedModel


class PersonalEmailDomain(TimeStampedModel):
    substring = models.TextField(unique=True)

    def __str__(self):
        return self.substring

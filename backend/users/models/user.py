from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator
from django.db import models

from core.fields import UniqueIDTextField

from users.validators import UsernameCharacterValidator, validate_username_not_reserved


class User(AbstractUser):
    """
    Authentication user model. Only contains auth-related fields.
    Custom user attributes belong on Profile model (user.profile.*).
    """

    external_id = UniqueIDTextField()
    email = models.EmailField(unique=True)
    username = models.CharField(
        max_length=150,
        unique=True,
        validators=[
            MinLengthValidator(4),
            UsernameCharacterValidator,
            validate_username_not_reserved,
        ],
        error_messages={"unique": "A user with that username already exists."},
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower("username"),
                name="users_user_username_ci_unique",
            ),
        ]

    def __str__(self):
        return self.email

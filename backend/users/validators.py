from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

# Character pattern validator - allows alphanumeric, dots, hyphens, underscores
UsernameCharacterValidator = RegexValidator(
    regex=r"^[a-zA-Z0-9._-]+$",
    message="Username can only contain letters, numbers, dots, hyphens, and underscores.",
)

# Reserved usernames that cannot be used
RESERVED_USERNAMES = [
    "hyperclast",
    "histre",
    "kiru",
    "k",
    "investor",
    "admin",
    "administrator",
    "root",
    "system",
    "api",
    "www",
    "mail",
    "support",
    "help",
    "info",
    "contact",
    "billing",
    "security",
    "noreply",
    "no-reply",
    "postmaster",
]


def validate_username_not_reserved(value):
    """Validate that the username is not in the reserved list."""
    if value.lower() in RESERVED_USERNAMES:
        raise ValidationError(
            f'The username "{value}" is reserved and cannot be used.',
            code="reserved_username",
        )

import random
import re

from django.contrib.auth import get_user_model


def generate_username_from_email(email: str, max_attempts: int = 10) -> str:
    """Generate a username from email address with 4 random digits.

    Takes the local part of the email (before @), sanitizes it to only allow
    alphanumeric, hyphens, and underscores, truncates to 16 chars, and appends
    4 random digits.

    Args:
        email: User's email address
        max_attempts: Number of attempts to find a unique username

    Returns:
        A unique username like "johnsmith1234"
    """
    User = get_user_model()

    local_part = email.split("@")[0].lower()
    sanitized = re.sub(r"[^a-z0-9._-]", "", local_part)

    if not sanitized:
        sanitized = "user"

    base = sanitized[:16]

    for _ in range(max_attempts):
        suffix = f"{random.randint(0, 9999):04d}"
        username = f"{base}{suffix}"

        if not User.objects.filter(username__iexact=username).exists():
            return username

    # Fallback: use shorter base with more randomness
    short_base = sanitized[:8]
    suffix = f"{random.randint(0, 99999999):08d}"
    return f"{short_base}{suffix}"[:20]

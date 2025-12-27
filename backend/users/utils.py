import random
import re

from django.contrib.auth import get_user_model

from .models import PersonalEmailDomain


PERSONAL_EMAIL_OVERRIDES = set()


def is_personal_email(email: str) -> bool:
    """Determines if an email address is from a personal email provider.

    Args:
        email: Full email address (e.g., "user@gmail.com")

    Returns:
        True if personal email, False if company/work email
    """
    if not email or "@" not in email:
        return True

    domain = email.split("@")[1].lower()

    if domain in PERSONAL_EMAIL_OVERRIDES:
        return True

    for substring in list(PersonalEmailDomain.objects.values_list("substring", flat=True)):
        if substring in domain:
            return True

    return False


def extract_org_name_from_domain(domain: str) -> str:
    """Extracts organization name from email domain.

    Rules:
    - Remove .com TLD (insstant.com -> insstant)
    - Keep other TLDs (insstant.co.uk -> insstant.co.uk, but just first part)
    - Handle subdomains (mail.company.com -> company)

    Args:
        domain: Email domain (e.g., "company.com")

    Returns:
        Organization name derived from domain
    """
    if not domain:
        return None

    domain = domain.lower().strip()

    parts = domain.split(".")

    if len(parts) < 2:
        return domain

    if parts[-1] == "com":
        if len(parts) == 2:
            return parts[0]
        else:
            return parts[-2]
    else:
        return parts[0]


def extract_domain_from_email(email: str) -> str | None:
    """Extracts domain from email address for org matching.

    Args:
        email: Full email address

    Returns:
        Domain string or None if personal email
    """
    if not email or "@" not in email:
        return None

    if is_personal_email(email):
        return None

    return email.split("@")[1].lower()


def compute_org_name_for_email(email: str) -> str:
    """Compute org name that would be created for an email address.

    For company emails: extract org name from domain (lowercase)
    For personal emails: use email local part

    Args:
        email: Full email address

    Returns:
        Organization name string
    """
    if is_personal_email(email):
        return email.split("@")[0] if "@" in email else "user"

    domain = extract_domain_from_email(email)
    if domain:
        org_name = extract_org_name_from_domain(domain)
        if org_name:
            return org_name

    return email.split("@")[0] if "@" in email else "user"


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

    short_base = sanitized[:8]
    suffix = f"{random.randint(0, 99999999):08d}"
    return f"{short_base}{suffix}"[:20]

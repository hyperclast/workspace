"""
Rate limiting utilities for external invitations.

Org members inviting each other = high trust, no limit needed.
External invitations (non-org members, non-existent users) = rate limited.

Note: We use Django's cache framework (not Django Ninja's @throttle decorator)
because we need conditional throttling based on request body content (the invited
email). Django Ninja throttles run before body parsing, so they can't implement
this business logic.
"""

from django.conf import settings
from django.core.cache import cache

from backend.utils import log_info, log_warning


def check_external_invitation_rate_limit(user, limit=10, window_seconds=3600):
    """
    Check if user has exceeded the rate limit for external invitations.

    Args:
        user: The user sending the invitation
        limit: Maximum invitations allowed in the time window (default: 10)
        window_seconds: Time window in seconds (default: 3600 = 1 hour)

    Returns:
        tuple: (allowed: bool, current_count: int, limit: int)
    """
    try:
        key = f"ext_invite_rate:{user.id}"

        # Get current count
        current_count = cache.get(key, 0)

        if current_count >= limit:
            return False, current_count, limit

        return True, current_count, limit
    except Exception as e:
        # If cache is unavailable, allow the request but log the error
        log_warning("Rate limit check failed (allowing request): %s", str(e))
        return True, 0, limit


def increment_external_invitation_count(user, window_seconds=3600):
    """
    Increment the external invitation count for a user.

    Args:
        user: The user sending the invitation
        window_seconds: Time window in seconds (default: 3600 = 1 hour)

    Returns:
        int: The new count after incrementing
    """
    try:
        key = f"ext_invite_rate:{user.id}"

        # Get current count, increment, and set with timeout
        current_count = cache.get(key, 0)
        new_count = current_count + 1
        cache.set(key, new_count, timeout=window_seconds)

        return new_count
    except Exception as e:
        log_warning("Rate limit increment failed: %s", str(e))
        return 0


def notify_admin_of_invitation_abuse(user, invitation_count, invited_email, context=""):
    """
    Notify admin when a user exceeds the external invitation rate limit.

    Args:
        user: The user who exceeded the limit
        invitation_count: Current invitation count
        invited_email: The email they tried to invite
        context: Additional context (e.g., "page" or "project")
    """
    from core.emailer import send_email

    log_warning(
        "ABUSE ALERT: User %s (id=%s) exceeded external invitation rate limit. "
        "Count=%s, attempted to invite=%s, context=%s",
        user.email,
        user.id,
        invitation_count,
        invited_email,
        context,
    )

    # Send email to admin
    try:
        admin_email = getattr(settings, "ADMINS", [])
        if admin_email:
            admin_email = admin_email[0][1] if isinstance(admin_email[0], tuple) else admin_email[0]
        else:
            admin_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)

        if admin_email:
            send_email(
                to=[admin_email],
                subject=f"[ABUSE ALERT] Invitation spam detected - {user.email}",
                body=f"""
Potential invitation spam detected:

User: {user.email} (ID: {user.id})
Invitation count this hour: {invitation_count}
Attempted to invite: {invited_email}
Context: {context}

Please investigate and consider banning this user if abuse is confirmed.
""",
            )
            log_info("Admin notified of invitation abuse by user %s", user.email)
    except Exception as e:
        log_warning("Failed to notify admin of invitation abuse: %s", str(e))

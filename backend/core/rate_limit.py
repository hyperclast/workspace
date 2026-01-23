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


def check_and_increment_rate_limit(user, limit=10, window_seconds=3600):
    """
    Atomically check and increment the rate limit counter.

    This function uses atomic cache operations to prevent TOCTOU race conditions
    where concurrent requests could exceed the rate limit by checking the count
    simultaneously before either increments it.

    Args:
        user: The user sending the invitation
        limit: Maximum invitations allowed in the time window (default: 10)
        window_seconds: Time window in seconds (default: 3600 = 1 hour)

    Returns:
        tuple: (allowed: bool, current_count: int, limit: int)
            - allowed: True if under limit (count was incremented), False if at/over limit
            - current_count: The count after this operation
            - limit: The configured limit (for error messages)
    """
    try:
        key = f"ext_invite_rate:{user.id}"

        # Use atomic incr which increments and returns the new value in one operation
        # This prevents race conditions between check and increment
        try:
            new_count = cache.incr(key)
        except ValueError:
            # Key doesn't exist - create it with initial value of 1
            # Use add() which only sets if key doesn't exist (atomic)
            # This handles the race where two requests both try to create the key
            if cache.add(key, 1, timeout=window_seconds):
                new_count = 1
            else:
                # Another request created it first, increment it
                new_count = cache.incr(key)

        # Check if we're over the limit AFTER incrementing
        if new_count > limit:
            # Optionally decrement to not count this failed attempt
            # (keeping count accurate for abuse detection)
            return False, new_count, limit

        return True, new_count, limit
    except Exception as e:
        # If cache is unavailable, allow the request but log the error
        log_warning("Rate limit check failed (allowing request): %s", str(e))
        return True, 0, limit


def check_external_invitation_rate_limit(user, limit=10, window_seconds=3600):
    """
    Check if user has exceeded the rate limit for external invitations.

    DEPRECATED: This function has a TOCTOU race condition. Use
    check_and_increment_rate_limit() instead for atomic check-and-increment.

    This function is kept for backward compatibility but now delegates to
    the atomic version. Note that it now increments the counter as part of
    the check, so increment_external_invitation_count() should NOT be called
    after this function returns True.

    Args:
        user: The user sending the invitation
        limit: Maximum invitations allowed in the time window (default: 10)
        window_seconds: Time window in seconds (default: 3600 = 1 hour)

    Returns:
        tuple: (allowed: bool, current_count: int, limit: int)
    """
    return check_and_increment_rate_limit(user, limit, window_seconds)


def increment_external_invitation_count(user, window_seconds=3600):
    """
    Increment the external invitation count for a user.

    DEPRECATED: This function is no longer needed because
    check_and_increment_rate_limit() (and check_external_invitation_rate_limit())
    now atomically increments the counter when the check passes.

    This function is kept for backward compatibility but is now a no-op.
    Callers should migrate to only using check_and_increment_rate_limit().

    Args:
        user: The user sending the invitation
        window_seconds: Time window in seconds (default: 3600 = 1 hour)

    Returns:
        int: 0 (no-op, count already incremented by check function)
    """
    # No-op: The counter is now incremented atomically in check_and_increment_rate_limit()
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

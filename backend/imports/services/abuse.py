"""
Import abuse tracking and enforcement service.

This module provides functions for recording abuse incidents and
determining if users should be blocked from importing.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Count
from django.utils import timezone

from imports.constants import Severity
from imports.models import ImportAbuseRecord, ImportBannedUser

logger = logging.getLogger(__name__)


def record_abuse(
    user,
    reason: str,
    details: dict,
    import_job=None,
    ip_address: str | None = None,
    user_agent: str = "",
) -> ImportAbuseRecord:
    """
    Record an abuse incident and determine severity.

    Args:
        user: The user who triggered the abuse detection.
        reason: Short identifier for the type of abuse (e.g., "compression_ratio").
        details: Full details from the inspection/detection.
        import_job: Optional ImportJob that triggered the detection.
        ip_address: IP address from request context.
        user_agent: User-Agent header from request context.

    Returns:
        The created ImportAbuseRecord.
    """
    severity = _calculate_severity(reason, details)

    record = ImportAbuseRecord.objects.create(
        user=user,
        import_job=import_job,
        reason=reason,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
        severity=severity,
    )

    # Log structured event for observability
    logger.error(
        "Import abuse detected: user=%s reason=%s severity=%s ip=%s",
        str(user.external_id),
        reason,
        severity,
        ip_address,
        extra={
            "user_id": str(user.external_id),
            "reason": reason,
            "severity": severity,
            "details": details,
            "ip_address": ip_address,
        },
    )

    return record


def _calculate_severity(reason: str, details: dict) -> str:
    """
    Determine severity based on violation type and magnitude.

    Args:
        reason: The type of abuse detected.
        details: Full details from the inspection.

    Returns:
        Severity level as a string.
    """
    ratio = details.get("compression_ratio", 0)

    # Critical: extreme ratios (>100x) strongly suggest intentional attack
    if ratio > 100:
        return Severity.CRITICAL

    # High: significant ratios or nested archive attempts
    if ratio > 50 or reason == "nested_archive":
        return Severity.HIGH

    # Medium: threshold violations
    if reason in ("compression_ratio", "extracted_size", "file_count"):
        return Severity.MEDIUM

    return Severity.LOW


def get_user_abuse_count(user, days: int = 30) -> int:
    """
    Count abuse records for user in time window.

    Args:
        user: The user to check.
        days: Number of days to look back.

    Returns:
        Count of abuse records in the time window.
    """
    since = timezone.now() - timedelta(days=days)
    return ImportAbuseRecord.objects.filter(
        user=user,
        created__gte=since,
    ).count()


def should_block_user(user) -> tuple[bool, str]:
    """
    Determine if user should be blocked from imports.

    Checks:
    1. Existing enforced ban in ImportBannedUser
    2. Threshold violations that would trigger a new ban

    Args:
        user: The user to check.

    Returns:
        Tuple of (should_block, reason).
    """
    # Check for existing enforced ban
    try:
        ban = ImportBannedUser.objects.get(user=user)
        if ban.enforced:
            return True, "import_banned"
    except ImportBannedUser.DoesNotExist:
        pass

    # Check thresholds and create ban if exceeded
    window_days = settings.WS_IMPORTS_ABUSE_WINDOW_DAYS
    since = timezone.now() - timedelta(days=window_days)

    # Count by severity
    counts = (
        ImportAbuseRecord.objects.filter(
            user=user,
            created__gte=since,
        )
        .values("severity")
        .annotate(count=Count("id"))
    )

    severity_counts = {item["severity"]: item["count"] for item in counts}

    # Check each threshold
    thresholds = [
        (Severity.CRITICAL, settings.WS_IMPORTS_ABUSE_CRITICAL_THRESHOLD, "critical_threshold_exceeded"),
        (Severity.HIGH, settings.WS_IMPORTS_ABUSE_HIGH_THRESHOLD, "high_threshold_exceeded"),
        (Severity.MEDIUM, settings.WS_IMPORTS_ABUSE_MEDIUM_THRESHOLD, "medium_threshold_exceeded"),
        (Severity.LOW, settings.WS_IMPORTS_ABUSE_LOW_THRESHOLD, "low_threshold_exceeded"),
    ]

    for severity, threshold, reason in thresholds:
        if severity_counts.get(severity, 0) >= threshold:
            # Create or update permanent ban
            _create_or_update_ban(user, reason, severity_counts)
            return True, reason

    return False, ""


def _create_or_update_ban(user, reason: str, severity_counts: dict) -> None:
    """
    Create or update a permanent ban record for the user.

    - If user has no ImportBannedUser entry, create one with the reason.
    - If user already has an ImportBannedUser entry, update the existing entry
      with the new reason and set enforced=True (re-enables lifted bans).
    """
    reason_text = f"Auto-banned: {reason}. Counts: {severity_counts}"

    ban, created = ImportBannedUser.objects.update_or_create(
        user=user,
        defaults={
            "reason": reason_text,
            "enforced": True,
        },
    )

    if created:
        logger.error(
            "Import ban created: user=%s reason=%s",
            str(user.external_id),
            reason,
            extra={
                "user_id": str(user.external_id),
                "reason": reason,
                "severity_counts": severity_counts,
            },
        )
    else:
        logger.error(
            "Import ban re-enabled: user=%s reason=%s",
            str(user.external_id),
            reason,
            extra={
                "user_id": str(user.external_id),
                "reason": reason,
                "severity_counts": severity_counts,
                "previous_ban_updated": True,
            },
        )

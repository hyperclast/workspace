"""
Tests for the import abuse tracking service.
"""

from datetime import timedelta
from unittest import TestCase as UnitTestCase
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from imports.constants import Severity
from imports.models import ImportAbuseRecord, ImportBannedUser
from imports.services.abuse import (
    _calculate_severity,
    _create_or_update_ban,
    get_user_abuse_count,
    record_abuse,
    should_block_user,
)
from imports.tests.factories import ImportAbuseRecordFactory, ImportBannedUserFactory, ImportJobFactory
from users.tests.factories import UserFactory


class TestCalculateSeverity(UnitTestCase):
    """Tests for _calculate_severity()."""

    def test_critical_for_extreme_ratio(self):
        """Returns CRITICAL for compression ratio > 100."""
        severity = _calculate_severity("compression_ratio", {"compression_ratio": 150.0})
        self.assertEqual(severity, Severity.CRITICAL)

    def test_high_for_high_ratio(self):
        """Returns HIGH for compression ratio > 50."""
        severity = _calculate_severity("compression_ratio", {"compression_ratio": 75.0})
        self.assertEqual(severity, Severity.HIGH)

    def test_high_for_nested_archive(self):
        """Returns HIGH for nested_archive reason."""
        severity = _calculate_severity("nested_archive", {})
        self.assertEqual(severity, Severity.HIGH)

    def test_medium_for_threshold_violations(self):
        """Returns MEDIUM for standard threshold violations."""
        self.assertEqual(
            _calculate_severity("compression_ratio", {"compression_ratio": 35.0}),
            Severity.MEDIUM,
        )
        self.assertEqual(
            _calculate_severity("extracted_size", {"uncompressed_size": 10**10}),
            Severity.MEDIUM,
        )
        self.assertEqual(
            _calculate_severity("file_count", {"file_count": 200000}),
            Severity.MEDIUM,
        )

    def test_low_for_unknown_reasons(self):
        """Returns LOW for unknown reasons."""
        severity = _calculate_severity("unknown_reason", {})
        self.assertEqual(severity, Severity.LOW)


class TestRecordAbuse(TestCase):
    """Tests for record_abuse()."""

    def test_creates_abuse_record(self):
        """Creates an ImportAbuseRecord with correct data."""
        user = UserFactory()
        job = ImportJobFactory(user=user)

        record = record_abuse(
            user=user,
            reason="compression_ratio",
            details={"compression_ratio": 50.0},
            import_job=job,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        self.assertIsInstance(record, ImportAbuseRecord)
        self.assertEqual(record.user, user)
        self.assertEqual(record.import_job, job)
        self.assertEqual(record.reason, "compression_ratio")
        self.assertEqual(record.details["compression_ratio"], 50.0)
        self.assertEqual(record.ip_address, "192.168.1.1")
        self.assertEqual(record.user_agent, "Mozilla/5.0")

    def test_calculates_severity_automatically(self):
        """Automatically calculates severity based on reason and details."""
        user = UserFactory()

        # Extreme ratio should be CRITICAL
        record = record_abuse(
            user=user,
            reason="compression_ratio",
            details={"compression_ratio": 200.0},
        )
        self.assertEqual(record.severity, Severity.CRITICAL)

    def test_works_without_import_job(self):
        """Can create record without associated import job."""
        user = UserFactory()

        record = record_abuse(
            user=user,
            reason="nested_archive",
            details={},
        )

        self.assertIsNone(record.import_job)
        self.assertEqual(record.reason, "nested_archive")

    def test_works_without_ip_and_user_agent(self):
        """Can create record without IP address and user agent."""
        user = UserFactory()

        record = record_abuse(
            user=user,
            reason="file_count",
            details={"file_count": 500000},
        )

        self.assertIsNone(record.ip_address)
        self.assertEqual(record.user_agent, "")


class TestGetUserAbuseCount(TestCase):
    """Tests for get_user_abuse_count()."""

    def test_counts_recent_abuse(self):
        """Counts abuse records within the time window."""
        user = UserFactory()
        ImportAbuseRecordFactory(user=user)
        ImportAbuseRecordFactory(user=user)
        ImportAbuseRecordFactory(user=user)

        count = get_user_abuse_count(user, days=30)

        self.assertEqual(count, 3)

    def test_ignores_other_users(self):
        """Does not count other users' abuse records."""
        user = UserFactory()
        other_user = UserFactory()

        ImportAbuseRecordFactory(user=user)
        ImportAbuseRecordFactory(user=other_user)
        ImportAbuseRecordFactory(user=other_user)

        count = get_user_abuse_count(user, days=30)

        self.assertEqual(count, 1)

    def test_ignores_old_records(self):
        """Does not count records older than the time window."""
        user = UserFactory()

        # Recent record
        ImportAbuseRecordFactory(user=user)

        # Old record (40 days ago)
        old_record = ImportAbuseRecordFactory(user=user)
        old_record.created = timezone.now() - timedelta(days=40)
        old_record.save(update_fields=["created"])

        count = get_user_abuse_count(user, days=30)

        self.assertEqual(count, 1)

    def test_custom_time_window(self):
        """Respects custom time window."""
        user = UserFactory()

        # Record 5 days ago
        recent_record = ImportAbuseRecordFactory(user=user)
        recent_record.created = timezone.now() - timedelta(days=5)
        recent_record.save(update_fields=["created"])

        # Record 10 days ago
        older_record = ImportAbuseRecordFactory(user=user)
        older_record.created = timezone.now() - timedelta(days=10)
        older_record.save(update_fields=["created"])

        # 7 day window should only include the 5-day-old record
        count = get_user_abuse_count(user, days=7)
        self.assertEqual(count, 1)

        # 14 day window should include both
        count = get_user_abuse_count(user, days=14)
        self.assertEqual(count, 2)


class TestShouldBlockUserWithExistingBan(TestCase):
    """Tests for should_block_user() with existing ImportBannedUser."""

    def test_blocks_user_with_enforced_ban(self):
        """Blocks user who has an enforced ImportBannedUser entry."""
        user = UserFactory()
        ImportBannedUserFactory(user=user, enforced=True)

        blocked, reason = should_block_user(user)

        self.assertTrue(blocked)
        self.assertEqual(reason, "import_banned")

    def test_does_not_block_user_with_lifted_ban(self):
        """Does not block user whose ban has been lifted."""
        user = UserFactory()
        ImportBannedUserFactory(user=user, enforced=False)

        blocked, reason = should_block_user(user)

        self.assertFalse(blocked)
        self.assertEqual(reason, "")


@override_settings(
    WS_IMPORTS_ABUSE_WINDOW_DAYS=7,
    WS_IMPORTS_ABUSE_CRITICAL_THRESHOLD=1,
    WS_IMPORTS_ABUSE_HIGH_THRESHOLD=2,
    WS_IMPORTS_ABUSE_MEDIUM_THRESHOLD=5,
    WS_IMPORTS_ABUSE_LOW_THRESHOLD=10,
)
class TestShouldBlockUserThresholds(TestCase):
    """Tests for should_block_user() threshold-based blocking."""

    def test_blocks_on_critical_threshold(self):
        """Blocks user when CRITICAL threshold is exceeded and creates ban."""
        user = UserFactory()
        ImportAbuseRecordFactory(user=user, severity=Severity.CRITICAL)

        blocked, reason = should_block_user(user)

        self.assertTrue(blocked)
        self.assertEqual(reason, "critical_threshold_exceeded")

        # Verify ban was created
        ban = ImportBannedUser.objects.get(user=user)
        self.assertTrue(ban.enforced)
        self.assertIn("critical_threshold_exceeded", ban.reason)

    def test_blocks_on_high_threshold(self):
        """Blocks user when HIGH threshold is exceeded."""
        user = UserFactory()
        ImportAbuseRecordFactory(user=user, severity=Severity.HIGH)
        ImportAbuseRecordFactory(user=user, severity=Severity.HIGH)

        blocked, reason = should_block_user(user)

        self.assertTrue(blocked)
        self.assertEqual(reason, "high_threshold_exceeded")

    def test_blocks_on_medium_threshold(self):
        """Blocks user when MEDIUM threshold is exceeded."""
        user = UserFactory()
        for _ in range(5):
            ImportAbuseRecordFactory(user=user, severity=Severity.MEDIUM)

        blocked, reason = should_block_user(user)

        self.assertTrue(blocked)
        self.assertEqual(reason, "medium_threshold_exceeded")

    def test_blocks_on_low_threshold(self):
        """Blocks user when LOW threshold is exceeded."""
        user = UserFactory()
        for _ in range(10):
            ImportAbuseRecordFactory(user=user, severity=Severity.LOW)

        blocked, reason = should_block_user(user)

        self.assertTrue(blocked)
        self.assertEqual(reason, "low_threshold_exceeded")

    def test_does_not_block_below_threshold(self):
        """Does not block user below all thresholds."""
        user = UserFactory()
        # 1 HIGH (threshold is 2)
        ImportAbuseRecordFactory(user=user, severity=Severity.HIGH)
        # 4 MEDIUM (threshold is 5)
        for _ in range(4):
            ImportAbuseRecordFactory(user=user, severity=Severity.MEDIUM)

        blocked, reason = should_block_user(user)

        self.assertFalse(blocked)
        self.assertEqual(reason, "")

    def test_does_not_block_clean_user(self):
        """Does not block user with no abuse records."""
        user = UserFactory()

        blocked, reason = should_block_user(user)

        self.assertFalse(blocked)
        self.assertEqual(reason, "")

    def test_ignores_old_abuse_records(self):
        """Does not count abuse records outside the window."""
        user = UserFactory()

        # Create CRITICAL record but make it old
        old_record = ImportAbuseRecordFactory(user=user, severity=Severity.CRITICAL)
        old_record.created = timezone.now() - timedelta(days=10)
        old_record.save(update_fields=["created"])

        blocked, reason = should_block_user(user)

        self.assertFalse(blocked)

    def test_critical_takes_precedence(self):
        """CRITICAL threshold is checked first."""
        user = UserFactory()

        # Create enough for all thresholds
        ImportAbuseRecordFactory(user=user, severity=Severity.CRITICAL)
        for _ in range(2):
            ImportAbuseRecordFactory(user=user, severity=Severity.HIGH)
        for _ in range(5):
            ImportAbuseRecordFactory(user=user, severity=Severity.MEDIUM)

        blocked, reason = should_block_user(user)

        self.assertTrue(blocked)
        self.assertEqual(reason, "critical_threshold_exceeded")


@override_settings(
    WS_IMPORTS_ABUSE_WINDOW_DAYS=14,
    WS_IMPORTS_ABUSE_CRITICAL_THRESHOLD=2,
)
class TestShouldBlockUserConfigurable(TestCase):
    """Tests for configurable threshold settings."""

    def test_uses_configured_window_days(self):
        """Uses WS_IMPORTS_ABUSE_WINDOW_DAYS setting."""
        user = UserFactory()

        # Create record 10 days ago (within 14-day window)
        record = ImportAbuseRecordFactory(user=user, severity=Severity.CRITICAL)
        record.created = timezone.now() - timedelta(days=10)
        record.save(update_fields=["created"])

        # Another recent one to meet threshold of 2
        ImportAbuseRecordFactory(user=user, severity=Severity.CRITICAL)

        blocked, reason = should_block_user(user)

        self.assertTrue(blocked)
        self.assertEqual(reason, "critical_threshold_exceeded")

    def test_uses_configured_threshold(self):
        """Uses configured threshold (2 for CRITICAL in this case)."""
        user = UserFactory()

        # Only 1 CRITICAL (threshold is 2)
        ImportAbuseRecordFactory(user=user, severity=Severity.CRITICAL)

        blocked, reason = should_block_user(user)

        self.assertFalse(blocked)


class TestCreateOrUpdateBan(TestCase):
    """Tests for _create_or_update_ban()."""

    def test_creates_new_ban(self):
        """Creates new ImportBannedUser when none exists."""
        user = UserFactory()

        _create_or_update_ban(user, "test_reason", {"critical": 1})

        ban = ImportBannedUser.objects.get(user=user)
        self.assertTrue(ban.enforced)
        self.assertIn("test_reason", ban.reason)
        self.assertIn("critical", ban.reason)

    def test_updates_existing_ban(self):
        """Updates existing ImportBannedUser with new reason."""
        user = UserFactory()
        existing_ban = ImportBannedUserFactory(user=user, reason="old_reason", enforced=False)

        _create_or_update_ban(user, "new_reason", {"high": 2})

        existing_ban.refresh_from_db()
        self.assertTrue(existing_ban.enforced)
        self.assertIn("new_reason", existing_ban.reason)
        self.assertNotIn("old_reason", existing_ban.reason)

    def test_re_enables_lifted_ban(self):
        """Re-enables a previously lifted ban."""
        user = UserFactory()
        ImportBannedUserFactory(user=user, enforced=False)

        _create_or_update_ban(user, "re_banned", {"medium": 5})

        ban = ImportBannedUser.objects.get(user=user)
        self.assertTrue(ban.enforced)

    def test_only_one_ban_per_user(self):
        """Ensures only one ImportBannedUser per user (update, not create new)."""
        user = UserFactory()
        ImportBannedUserFactory(user=user)

        _create_or_update_ban(user, "second_ban", {"low": 10})

        self.assertEqual(ImportBannedUser.objects.filter(user=user).count(), 1)


@override_settings(
    WS_IMPORTS_ABUSE_WINDOW_DAYS=7,
    WS_IMPORTS_ABUSE_CRITICAL_THRESHOLD=1,
    WS_IMPORTS_ABUSE_HIGH_THRESHOLD=2,
    WS_IMPORTS_ABUSE_MEDIUM_THRESHOLD=5,
    WS_IMPORTS_ABUSE_LOW_THRESHOLD=10,
)
class TestBanReEnablement(TestCase):
    """Tests for ban re-enablement after being lifted."""

    def test_lifted_ban_re_enabled_on_new_violation(self):
        """A lifted ban is re-enabled when user exceeds threshold again."""
        user = UserFactory()

        # Create and lift a ban
        ImportBannedUserFactory(user=user, enforced=False, reason="old_reason")

        # User abuses again
        ImportAbuseRecordFactory(user=user, severity=Severity.CRITICAL)

        blocked, reason = should_block_user(user)

        self.assertTrue(blocked)
        self.assertEqual(reason, "critical_threshold_exceeded")

        # Verify ban was re-enabled
        ban = ImportBannedUser.objects.get(user=user)
        self.assertTrue(ban.enforced)
        self.assertIn("critical_threshold_exceeded", ban.reason)


@override_settings(
    WS_IMPORTS_ABUSE_WINDOW_DAYS=7,
    WS_IMPORTS_ABUSE_CRITICAL_THRESHOLD=2,
    WS_IMPORTS_ABUSE_HIGH_THRESHOLD=3,
    WS_IMPORTS_ABUSE_MEDIUM_THRESHOLD=5,
    WS_IMPORTS_ABUSE_LOW_THRESHOLD=10,
)
class TestRapidImportAttempts(TestCase):
    """Tests for ban enforcement across multiple import attempts in quick succession."""

    def test_rapid_violations_trigger_ban(self):
        """Multiple rapid violations should trigger a ban once threshold is reached."""
        user = UserFactory()

        # First CRITICAL violation - not enough for ban (threshold is 2)
        record_abuse(
            user=user,
            reason="compression_ratio",
            details={"compression_ratio": 150.0},  # CRITICAL
        )

        blocked, reason = should_block_user(user)
        self.assertFalse(blocked)  # Not yet banned

        # Second CRITICAL violation - should now trigger ban
        record_abuse(
            user=user,
            reason="compression_ratio",
            details={"compression_ratio": 200.0},  # CRITICAL
        )

        blocked, reason = should_block_user(user)
        self.assertTrue(blocked)
        self.assertEqual(reason, "critical_threshold_exceeded")

        # Verify ban was created
        self.assertTrue(ImportBannedUser.objects.filter(user=user, enforced=True).exists())

    def test_rapid_attempts_from_different_ips_still_counts(self):
        """Abuse tracking is user-based, not IP-based, so different IPs still count."""
        user = UserFactory()

        # Violations from different IPs
        record_abuse(
            user=user,
            reason="compression_ratio",
            details={"compression_ratio": 150.0},
            ip_address="192.168.1.1",
        )
        record_abuse(
            user=user,
            reason="compression_ratio",
            details={"compression_ratio": 160.0},
            ip_address="10.0.0.1",
        )

        blocked, reason = should_block_user(user)

        self.assertTrue(blocked)
        self.assertEqual(reason, "critical_threshold_exceeded")

    def test_rapid_attempts_after_ban_still_blocked(self):
        """Once banned, subsequent attempts should still be blocked."""
        user = UserFactory()

        # Create enough violations to get banned
        ImportAbuseRecordFactory(user=user, severity=Severity.CRITICAL)
        ImportAbuseRecordFactory(user=user, severity=Severity.CRITICAL)

        # First check - should get banned
        blocked, reason = should_block_user(user)
        self.assertTrue(blocked)

        # More violations after ban
        record_abuse(
            user=user,
            reason="nested_archive",
            details={},
        )

        # Should still be blocked
        blocked, reason = should_block_user(user)
        self.assertTrue(blocked)
        self.assertEqual(reason, "import_banned")  # Now shows as "import_banned" since ban exists


@override_settings(
    WS_IMPORTS_ABUSE_WINDOW_DAYS=7,
    WS_IMPORTS_ABUSE_CRITICAL_THRESHOLD=1,
    WS_IMPORTS_ABUSE_HIGH_THRESHOLD=2,
    WS_IMPORTS_ABUSE_MEDIUM_THRESHOLD=5,
    WS_IMPORTS_ABUSE_LOW_THRESHOLD=10,
)
class TestBanLiftAndReban(TestCase):
    """Tests for ban lift and subsequent re-ban behavior."""

    def test_ban_can_be_lifted(self):
        """A ban can be lifted by setting enforced=False."""
        user = UserFactory()
        ban = ImportBannedUserFactory(user=user, enforced=True, reason="original_ban")

        # Lift the ban
        ban.enforced = False
        ban.save(update_fields=["enforced"])

        # User should no longer be blocked (assuming no new violations)
        blocked, reason = should_block_user(user)

        # User not blocked if no new violations exceed threshold
        # But if old violations are still in window, may still get blocked
        # Let's verify with clean slate
        ImportAbuseRecord.objects.filter(user=user).delete()

        blocked, reason = should_block_user(user)
        self.assertFalse(blocked)

    def test_re_ban_after_lift_updates_reason(self):
        """When a lifted ban is re-enabled, the reason should be updated."""
        user = UserFactory()

        # Create and lift a ban
        ban = ImportBannedUserFactory(user=user, enforced=False, reason="old_violation")

        # Create new violation that exceeds threshold
        ImportAbuseRecordFactory(user=user, severity=Severity.CRITICAL)

        blocked, reason = should_block_user(user)

        self.assertTrue(blocked)
        self.assertEqual(reason, "critical_threshold_exceeded")

        # Verify the ban record was updated, not a new one created
        self.assertEqual(ImportBannedUser.objects.filter(user=user).count(), 1)
        ban.refresh_from_db()
        self.assertTrue(ban.enforced)
        self.assertIn("critical_threshold_exceeded", ban.reason)
        self.assertNotIn("old_violation", ban.reason)

    def test_multiple_lift_reban_cycles(self):
        """Multiple lift/re-ban cycles work correctly."""
        user = UserFactory()

        # Cycle 1: Get banned
        ImportAbuseRecordFactory(user=user, severity=Severity.CRITICAL)
        blocked, reason = should_block_user(user)
        self.assertTrue(blocked)

        # Cycle 1: Lift ban and clear records
        ban = ImportBannedUser.objects.get(user=user)
        ban.enforced = False
        ban.save(update_fields=["enforced"])
        ImportAbuseRecord.objects.filter(user=user).delete()

        # Verify unblocked
        blocked, _ = should_block_user(user)
        self.assertFalse(blocked)

        # Cycle 2: New violation and re-ban
        ImportAbuseRecordFactory(user=user, severity=Severity.CRITICAL)
        blocked, reason = should_block_user(user)
        self.assertTrue(blocked)
        self.assertEqual(reason, "critical_threshold_exceeded")

        # Cycle 2: Lift again
        ban.refresh_from_db()
        ban.enforced = False
        ban.save(update_fields=["enforced"])
        ImportAbuseRecord.objects.filter(user=user).delete()

        # Should be unblocked again
        blocked, _ = should_block_user(user)
        self.assertFalse(blocked)

    def test_ban_persists_across_window_reset(self):
        """Even if abuse records age out of window, enforced ban remains."""
        user = UserFactory()

        # Create ban
        ImportBannedUserFactory(user=user, enforced=True, reason="permanent_ban")

        # Create an old abuse record outside the window
        old_record = ImportAbuseRecordFactory(user=user, severity=Severity.CRITICAL)
        old_record.created = timezone.now() - timedelta(days=30)  # Outside 7-day window
        old_record.save(update_fields=["created"])

        # User should still be blocked due to enforced ban
        blocked, reason = should_block_user(user)

        self.assertTrue(blocked)
        self.assertEqual(reason, "import_banned")

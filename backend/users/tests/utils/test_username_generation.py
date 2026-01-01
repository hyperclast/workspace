from django.test import TestCase

from users.tests.factories import UserFactory
from users.utils import generate_username_from_email


class TestGenerateUsernameFromEmail(TestCase):
    def test_basic_email(self):
        username = generate_username_from_email("john@example.com")

        self.assertTrue(username.startswith("john"))
        self.assertEqual(len(username), 8)  # john + 4 digits

    def test_email_with_dots_preserved(self):
        username = generate_username_from_email("john.smith@example.com")

        self.assertTrue(username.startswith("john.smith"))

    def test_email_with_plus(self):
        username = generate_username_from_email("john+test@example.com")

        self.assertTrue(username.startswith("johntest"))

    def test_email_with_special_chars(self):
        username = generate_username_from_email("john!#$%smith@example.com")

        self.assertTrue(username.startswith("johnsmith"))

    def test_long_email_truncated(self):
        username = generate_username_from_email("verylongemailaddresspart@example.com")

        self.assertEqual(len(username), 20)  # 16 base + 4 digits

    def test_username_is_lowercase(self):
        username = generate_username_from_email("JohnSmith@example.com")

        self.assertTrue(username.startswith("johnsmith"))
        self.assertEqual(username, username.lower())

    def test_avoids_collision(self):
        UserFactory(username="testuser1234")

        username = generate_username_from_email("testuser@example.com")

        self.assertTrue(username.startswith("testuser"))
        self.assertNotEqual(username, "testuser1234")

    def test_case_insensitive_collision_check(self):
        UserFactory(username="TestUser1234")

        username = generate_username_from_email("testuser@example.com")

        self.assertNotEqual(username.lower(), "testuser1234")

    def test_empty_local_part_fallback(self):
        username = generate_username_from_email("@example.com")

        self.assertTrue(username.startswith("user"))

    def test_only_special_chars_fallback(self):
        username = generate_username_from_email("!!!@example.com")

        self.assertTrue(username.startswith("user"))

    def test_preserves_hyphens_underscores(self):
        username = generate_username_from_email("john-smith_jr@example.com")

        self.assertTrue(username.startswith("john-smith_jr"))

    def test_single_char_email_still_meets_minimum_length(self):
        """Username should be at least 4 chars even with single-char email local part."""
        username = generate_username_from_email("a@example.com")

        self.assertTrue(len(username) >= 4)
        self.assertTrue(username.startswith("a"))

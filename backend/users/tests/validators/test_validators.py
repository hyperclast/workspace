from django.core.exceptions import ValidationError
from django.test import TestCase

from users.validators import (
    RESERVED_USERNAMES,
    UsernameCharacterValidator,
    validate_username_not_reserved,
)


class TestUsernameCharacterValidator(TestCase):
    def test_allows_alphanumeric(self):
        UsernameCharacterValidator("username123")

    def test_allows_dots(self):
        UsernameCharacterValidator("user.name")

    def test_allows_hyphens(self):
        UsernameCharacterValidator("user-name")

    def test_allows_underscores(self):
        UsernameCharacterValidator("user_name")

    def test_allows_mixed_case(self):
        UsernameCharacterValidator("UserName")

    def test_rejects_spaces(self):
        with self.assertRaises(ValidationError):
            UsernameCharacterValidator("user name")

    def test_rejects_at_symbol(self):
        with self.assertRaises(ValidationError):
            UsernameCharacterValidator("user@name")

    def test_rejects_special_chars(self):
        with self.assertRaises(ValidationError):
            UsernameCharacterValidator("user!name")

    def test_rejects_unicode(self):
        with self.assertRaises(ValidationError):
            UsernameCharacterValidator("usérname")


class TestReservedUsernameValidator(TestCase):
    def test_allows_normal_username(self):
        validate_username_not_reserved("johndoe")

    def test_rejects_admin(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_username_not_reserved("admin")
        self.assertIn("reserved", str(ctx.exception).lower())

    def test_rejects_hyperclast(self):
        with self.assertRaises(ValidationError):
            validate_username_not_reserved("hyperclast")

    def test_rejects_histre(self):
        with self.assertRaises(ValidationError):
            validate_username_not_reserved("histre")

    def test_case_insensitive_rejection(self):
        with self.assertRaises(ValidationError):
            validate_username_not_reserved("ADMIN")

    def test_case_insensitive_rejection_mixed(self):
        with self.assertRaises(ValidationError):
            validate_username_not_reserved("HyperClast")

    def test_reserved_list_contains_expected_entries(self):
        expected = ["hyperclast", "histre", "admin", "root", "system", "api", "support"]
        for name in expected:
            self.assertIn(name, RESERVED_USERNAMES)

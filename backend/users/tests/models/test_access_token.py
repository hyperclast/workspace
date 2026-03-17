from django.db import IntegrityError
from django.test import TestCase

from users.constants import AccessTokenManagedBy
from users.models import AccessToken
from users.tests.factories import UserFactory


class TestAccessTokenModel(TestCase):
    def test_creation_with_defaults(self):
        user = UserFactory()
        token = AccessToken.objects.create(user=user)

        self.assertIsNotNone(token.id)
        self.assertIsNotNone(token.value)
        self.assertTrue(len(token.value) > 0)
        self.assertEqual(token.label, "")
        self.assertEqual(token.managed_by, AccessTokenManagedBy.USER)
        self.assertTrue(token.is_active)
        self.assertFalse(token.is_default)
        self.assertIsNotNone(token.created)
        self.assertIsNotNone(token.modified)

    def test_value_is_unique(self):
        user = UserFactory()
        token1 = AccessToken.objects.create(user=user)
        token2 = AccessToken.objects.create(user=user)

        self.assertNotEqual(token1.value, token2.value)

    def test_value_unique_constraint(self):
        user = UserFactory()
        token = AccessToken.objects.create(user=user)

        with self.assertRaises(IntegrityError):
            AccessToken.objects.create(user=user, value=token.value)

    def test_system_managed_token(self):
        user = UserFactory()
        token = AccessToken.objects.create(
            user=user,
            managed_by=AccessTokenManagedBy.SYSTEM,
        )

        self.assertEqual(token.managed_by, AccessTokenManagedBy.SYSTEM)

    def test_user_managed_token_with_label(self):
        user = UserFactory()
        token = AccessToken.objects.create(
            user=user,
            managed_by=AccessTokenManagedBy.USER,
            label="Deploy Script",
        )

        self.assertEqual(token.label, "Deploy Script")
        self.assertEqual(token.managed_by, AccessTokenManagedBy.USER)

    def test_deactivation(self):
        user = UserFactory()
        token = AccessToken.objects.create(user=user)

        token.is_active = False
        token.save(update_fields=["is_active", "modified"])

        token.refresh_from_db()
        self.assertFalse(token.is_active)

    def test_cascade_on_user_delete(self):
        user = UserFactory()
        # Signal creates 1 default token; we add 2 more manually = 3 total
        AccessToken.objects.create(user=user)
        AccessToken.objects.create(user=user)
        user_id = user.id

        self.assertEqual(AccessToken.objects.filter(user_id=user_id).count(), 3)

        user.delete()

        self.assertEqual(AccessToken.objects.filter(user_id=user_id).count(), 0)

    def test_str_representation(self):
        user = UserFactory()
        token = AccessToken.objects.create(user=user, managed_by=AccessTokenManagedBy.SYSTEM)

        self.assertIn("system", str(token))
        self.assertIn(str(user), str(token))

    def test_multiple_tokens_per_user(self):
        user = UserFactory()
        # Signal creates 1 default token; we add 2 more manually = 3 total
        token1 = AccessToken.objects.create(user=user, label="Token 1")
        token2 = AccessToken.objects.create(user=user, label="Token 2")

        tokens = AccessToken.objects.filter(user=user)
        self.assertEqual(tokens.count(), 3)
        self.assertNotEqual(token1.value, token2.value)


class TestIsDefaultField(TestCase):
    """Test is_default field behavior and database constraints."""

    def test_default_token_created_by_signal(self):
        """user_post_save signal creates a default user-managed token."""
        user = UserFactory()
        default_token = AccessToken.objects.get(
            user=user,
            managed_by=AccessTokenManagedBy.USER,
            is_default=True,
            is_active=True,
        )
        self.assertEqual(default_token.label, "Default")

    def test_is_default_defaults_to_false(self):
        """Manually created tokens default to is_default=False."""
        user = UserFactory()
        token = AccessToken.objects.create(user=user)
        self.assertFalse(token.is_default)

    def test_unique_constraint_prevents_second_active_default(self):
        """Only one active, user-managed, default token per user."""
        user = UserFactory()
        # Signal already created one default; creating another should fail
        with self.assertRaises(IntegrityError):
            AccessToken.objects.create(
                user=user,
                managed_by=AccessTokenManagedBy.USER,
                is_default=True,
                is_active=True,
            )

    def test_system_token_cannot_be_default(self):
        """CHECK constraint prevents system-managed tokens from being default."""
        user = UserFactory()
        with self.assertRaises(IntegrityError):
            AccessToken.objects.create(
                user=user,
                managed_by=AccessTokenManagedBy.SYSTEM,
                is_default=True,
            )

    def test_deactivated_default_allows_new_default(self):
        """Deactivating the old default allows creating a new one."""
        user = UserFactory()
        old_default = AccessToken.objects.get(user=user, is_default=True, is_active=True)
        old_default.is_active = False
        old_default.save(update_fields=["is_active", "modified"])

        new_default = AccessToken.objects.create(
            user=user,
            managed_by=AccessTokenManagedBy.USER,
            is_default=True,
            is_active=True,
        )
        self.assertTrue(new_default.is_default)
        self.assertTrue(new_default.is_active)


class TestAccessTokenManager(TestCase):
    """Test AccessTokenManager methods."""

    def test_get_default_token_value_returns_value(self):
        user = UserFactory()
        default_token = AccessToken.objects.get(user=user, is_default=True)
        result = AccessToken.objects.get_default_token_value(user.id)
        self.assertEqual(result, default_token.value)

    def test_get_default_token_value_returns_none_when_no_default(self):
        user = UserFactory()
        # Deactivate the signal-created default
        AccessToken.objects.filter(user=user, is_default=True).update(is_active=False)
        result = AccessToken.objects.get_default_token_value(user.id)
        self.assertIsNone(result)

    def test_get_default_token_value_ignores_deactivated(self):
        """Deactivated default tokens are not returned."""
        user = UserFactory()
        AccessToken.objects.filter(user=user, is_default=True).update(is_active=False)
        result = AccessToken.objects.get_default_token_value(user.id)
        self.assertIsNone(result)

    def test_get_default_token_value_ignores_system_tokens(self):
        """System-managed tokens are never returned as default."""
        user = UserFactory()
        # Deactivate the user-managed default
        AccessToken.objects.filter(user=user, is_default=True).update(is_active=False)
        # System token exists but should not be returned
        AccessToken.objects.create(user=user, managed_by=AccessTokenManagedBy.SYSTEM, is_active=True)
        result = AccessToken.objects.get_default_token_value(user.id)
        self.assertIsNone(result)

    def test_get_default_token_returns_instance(self):
        user = UserFactory()
        token = AccessToken.objects.get_default_token(user.id)
        self.assertIsNotNone(token)
        self.assertTrue(token.is_default)
        self.assertTrue(token.is_active)
        self.assertEqual(token.managed_by, AccessTokenManagedBy.USER)

    def test_get_default_token_returns_none_when_no_default(self):
        user = UserFactory()
        AccessToken.objects.filter(user=user, is_default=True).update(is_active=False)
        token = AccessToken.objects.get_default_token(user.id)
        self.assertIsNone(token)

    def test_regenerate_default_token_replaces_value(self):
        user = UserFactory()
        old_value = AccessToken.objects.get_default_token_value(user.id)

        token_obj = AccessToken.objects.regenerate_default_token(user)

        self.assertNotEqual(token_obj.value, old_value)
        self.assertTrue(token_obj.is_default)
        self.assertTrue(token_obj.is_active)
        # Verify persisted to DB
        self.assertEqual(
            AccessToken.objects.get_default_token_value(user.id),
            token_obj.value,
        )

    def test_regenerate_default_token_creates_when_none_exists(self):
        user = UserFactory()
        # Remove the signal-created default
        AccessToken.objects.filter(user=user, is_default=True).delete()

        token_obj = AccessToken.objects.regenerate_default_token(user)

        self.assertTrue(token_obj.is_default)
        self.assertTrue(token_obj.is_active)
        self.assertEqual(token_obj.managed_by, AccessTokenManagedBy.USER)
        self.assertEqual(token_obj.label, "Default")

    def test_get_user_tokens_returns_only_user_managed(self):
        user = UserFactory()
        # Signal created 1 user-managed default; add 1 more user + 1 system
        AccessToken.objects.create(user=user, managed_by=AccessTokenManagedBy.USER, label="Extra")
        AccessToken.objects.create(user=user, managed_by=AccessTokenManagedBy.SYSTEM)

        tokens = AccessToken.objects.get_user_tokens(user.id)
        self.assertEqual(tokens.count(), 2)
        for token in tokens:
            self.assertEqual(token.managed_by, AccessTokenManagedBy.USER)

    def test_get_user_tokens_ordered_by_newest_first(self):
        user = UserFactory()
        # Signal created "Default"; add another
        extra = AccessToken.objects.create(user=user, managed_by=AccessTokenManagedBy.USER, label="Extra")

        tokens = list(AccessToken.objects.get_user_tokens(user.id))
        # Most recently created should be first
        self.assertEqual(tokens[0].id, extra.id)

    def test_get_user_tokens_excludes_other_users(self):
        user1 = UserFactory()
        user2 = UserFactory()
        AccessToken.objects.create(user=user2, managed_by=AccessTokenManagedBy.USER, label="Other")

        tokens = AccessToken.objects.get_user_tokens(user1.id)
        for token in tokens:
            self.assertEqual(token.user_id, user1.id)

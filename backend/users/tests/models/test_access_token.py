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
        AccessToken.objects.create(user=user)
        AccessToken.objects.create(user=user)
        user_id = user.id

        self.assertEqual(AccessToken.objects.filter(user_id=user_id).count(), 2)

        user.delete()

        self.assertEqual(AccessToken.objects.filter(user_id=user_id).count(), 0)

    def test_str_representation(self):
        user = UserFactory()
        token = AccessToken.objects.create(user=user, managed_by=AccessTokenManagedBy.SYSTEM)

        self.assertIn("system", str(token))
        self.assertIn(str(user), str(token))

    def test_multiple_tokens_per_user(self):
        user = UserFactory()
        token1 = AccessToken.objects.create(user=user, label="Token 1")
        token2 = AccessToken.objects.create(user=user, label="Token 2")

        tokens = AccessToken.objects.filter(user=user)
        self.assertEqual(tokens.count(), 2)
        self.assertNotEqual(token1.value, token2.value)

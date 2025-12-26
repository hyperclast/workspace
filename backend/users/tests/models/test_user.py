from django.test import TestCase

from users.tests.factories import UserFactory


class TestUserModel(TestCase):
    def test_user_creation(self):
        user = UserFactory()

        self.assertIsNotNone(user.profile)

import uuid

from django.test import SimpleTestCase

from core.helpers import is_valid_uuid


class TestIsValidUUID(SimpleTestCase):
    """Tests helper `is_valid_uuid`.

    The helper guards `filter(uuid_field__in=[...])` calls against malformed
    external IDs that would otherwise raise DataError on Postgres, so its
    contract on non-string / falsy / malformed input is load-bearing.
    """

    def test_canonical_uuid_string(self):
        self.assertTrue(is_valid_uuid(str(uuid.uuid4())))

    def test_uppercase_uuid_string(self):
        self.assertTrue(is_valid_uuid(str(uuid.uuid4()).upper()))

    def test_uuid_without_hyphens(self):
        self.assertTrue(is_valid_uuid(uuid.uuid4().hex))

    def test_non_uuid_string(self):
        self.assertFalse(is_valid_uuid("not-a-uuid"))

    def test_empty_string(self):
        self.assertFalse(is_valid_uuid(""))

    def test_none(self):
        self.assertFalse(is_valid_uuid(None))

    def test_integer(self):
        self.assertFalse(is_valid_uuid(12345))

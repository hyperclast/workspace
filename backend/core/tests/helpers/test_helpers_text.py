from unittest.mock import patch

from django.test import SimpleTestCase

from core.helpers import generate_external_id, generate_random_string, hashify


@patch("core.helpers.text.generate_random_string")
@patch("core.helpers.text.hashify")
class TestGenerateExternalIDHelper(SimpleTestCase):
    """Tests helper func `generate_external_id`."""

    def test_generate_external_id_defaults(self, mock_hash, mock_random):
        random_str = "abcde12345"
        hash_str = "wxyz67890"
        mock_random.return_value = random_str
        mock_hash.return_value = hash_str

        result = generate_external_id()

        mock_random.assert_called_once_with(10)
        self.assertFalse(mock_hash.called)
        self.assertEqual(result, random_str)

    def test_generate_external_id_length(self, mock_hash, mock_random):
        random_str = "abcde1234567"
        hash_str = "wxyz6789012"
        mock_random.return_value = random_str
        mock_hash.return_value = hash_str
        length = 12

        result = generate_external_id(length)

        mock_random.assert_called_once_with(length)
        self.assertFalse(mock_hash.called)
        self.assertEqual(result, random_str)

    def test_generate_external_id_defaults_hash(self, mock_hash, mock_random):
        random_str = "abcde12345"
        hash_str = "wxyz67890"
        mock_random.return_value = random_str
        mock_hash.return_value = hash_str
        data = "rownum"

        result = generate_external_id(data=data)

        self.assertFalse(mock_random.called)
        mock_hash.assert_called_once_with(data, 10)
        self.assertEqual(result, hash_str)

    def test_generate_external_id_length_hash(self, mock_hash, mock_random):
        random_str = "abcde1234567"
        hash_str = "wxyz6789012"
        mock_random.return_value = random_str
        mock_hash.return_value = hash_str
        length = 12
        data = "rownum"

        result = generate_external_id(length, data)

        self.assertFalse(mock_random.called)
        mock_hash.assert_called_once_with(data, length)
        self.assertEqual(result, hash_str)


class TestHashifyHelper(SimpleTestCase):
    """Tests helper `hashify`."""

    def test_hashify_no_length(self):
        data = "rownum"

        result = hashify(data)

        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 10)

    def test_hashify_with_length(self):
        length = 12
        data = "rownum"

        result = hashify(data, length)

        self.assertIsInstance(result, str)
        self.assertEqual(len(result), length)


class TestGenerateRandomStringHelper(SimpleTestCase):
    """Tests `generate_random_string`."""

    def test_generate_random_string_default_length(self):
        result = generate_random_string()

        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 10)

    def test_generate_random_string_with_length(self):
        length = 14

        result = generate_random_string(length)

        self.assertIsInstance(result, str)
        self.assertEqual(len(result), length)

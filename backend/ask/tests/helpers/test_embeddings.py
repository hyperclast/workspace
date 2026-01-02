"""
Tests for ask.helpers.embeddings module.
"""

from unittest.mock import Mock, patch

from django.conf import settings
from django.test import TestCase
from litellm import RateLimitError, Timeout

from ask.helpers.embeddings import (
    compute_embedding,
    create_embedding,
    truncate_input_data,
)


class TestCreateEmbedding(TestCase):
    """Test the create_embedding function."""

    @patch("ask.helpers.embeddings.embedding")
    def test_create_embedding_with_api_key(self, mock_embedding):
        """Test creating an embedding with an API key."""
        # Setup mock
        mock_response = Mock()
        mock_response.data = [{"embedding": [0.1, 0.2, 0.3]}]
        mock_embedding.return_value = mock_response

        # Call function
        result = create_embedding("test input", api_key="test-api-key")

        # Verify
        self.assertEqual(result, [0.1, 0.2, 0.3])
        mock_embedding.assert_called_once_with(
            input=["test input"],
            model=settings.ASK_EMBEDDINGS_DEFAULT_MODEL,
            api_key="test-api-key",
        )

    def test_create_embedding_requires_api_key(self):
        """Test that create_embedding raises error without API key."""
        with self.assertRaises(ValueError) as context:
            create_embedding("test input")

        self.assertIn("api_key is required", str(context.exception))

    @patch("ask.helpers.embeddings.embedding")
    def test_create_embedding_with_custom_model(self, mock_embedding):
        """Test creating an embedding with a custom model."""
        # Setup mock
        mock_response = Mock()
        mock_response.data = [{"embedding": [0.4, 0.5, 0.6]}]
        mock_embedding.return_value = mock_response

        # Call function with custom model
        result = create_embedding("test input", model="custom-model", api_key="test-key")

        # Verify
        self.assertEqual(result, [0.4, 0.5, 0.6])
        mock_embedding.assert_called_once_with(
            input=["test input"],
            model="custom-model",
            api_key="test-key",
        )

    @patch("ask.helpers.embeddings.embedding")
    @patch("core.helpers.errors.time.sleep")
    def test_create_embedding_retries_on_rate_limit(self, mock_sleep, mock_embedding):
        """Test that create_embedding retries on RateLimitError."""
        # Setup mock to fail once then succeed
        mock_response = Mock()
        mock_response.data = [{"embedding": [0.1, 0.2, 0.3]}]
        mock_embedding.side_effect = [RateLimitError("Rate limit", "openai", "text-embedding-3-small"), mock_response]

        # Call function
        result = create_embedding("test input", api_key="test-key")

        # Verify it retried and succeeded
        self.assertEqual(result, [0.1, 0.2, 0.3])
        self.assertEqual(mock_embedding.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("ask.helpers.embeddings.embedding")
    @patch("core.helpers.errors.time.sleep")
    def test_create_embedding_retries_on_timeout(self, mock_sleep, mock_embedding):
        """Test that create_embedding retries on Timeout."""
        # Setup mock to fail once then succeed
        mock_response = Mock()
        mock_response.data = [{"embedding": [0.1, 0.2, 0.3]}]
        mock_embedding.side_effect = [Timeout("Timeout error", "text-embedding-3-small", "openai"), mock_response]

        # Call function
        result = create_embedding("test input", api_key="test-key")

        # Verify it retried and succeeded
        self.assertEqual(result, [0.1, 0.2, 0.3])
        self.assertEqual(mock_embedding.call_count, 2)
        mock_sleep.assert_called_once()


class TestTruncateInputData(TestCase):
    """Test the truncate_input_data function."""

    def test_truncate_input_data_below_limit(self):
        """Test that data below the token limit is not truncated."""
        data = "This is a short text."
        result = truncate_input_data(data, encoding_name="cl100k_base", max_tokens=100)

        # Should return original data
        self.assertEqual(result, data)

    def test_truncate_input_data_above_limit(self):
        """Test that data above the token limit is truncated."""
        # Create a long string that will exceed token limit
        data = "This is a test. " * 100
        result = truncate_input_data(data, encoding_name="cl100k_base", max_tokens=10)

        # Should be truncated
        self.assertLess(len(result), len(data))
        # Should not be empty
        self.assertGreater(len(result), 0)

    def test_truncate_input_data_exactly_at_limit(self):
        """Test that data exactly at the token limit is not truncated."""
        # Use a simple string and calculate its token count
        data = "Hello world"

        # First, get the actual token count
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
        actual_tokens = len(encoding.encode(data))

        # Truncate with exact token count
        result = truncate_input_data(data, encoding_name="cl100k_base", max_tokens=actual_tokens)

        # Should return original data
        self.assertEqual(result, data)

    def test_truncate_input_data_empty_string(self):
        """Test that empty string is handled correctly."""
        data = ""
        result = truncate_input_data(data, encoding_name="cl100k_base", max_tokens=100)

        # Should return empty string
        self.assertEqual(result, "")

    def test_truncate_input_data_special_characters(self):
        """Test that special characters are handled correctly."""
        data = "Hello world! Testing special chars: @#$%^&*()"
        result = truncate_input_data(data, encoding_name="cl100k_base", max_tokens=2)

        # Should be truncated but valid
        self.assertLessEqual(len(result), len(data))
        # Should not raise encoding errors
        self.assertIsInstance(result, str)


class TestComputeEmbedding(TestCase):
    """Test the compute_embedding function."""

    @patch("ask.helpers.embeddings.create_embedding")
    @patch("ask.helpers.embeddings.truncate_input_data")
    def test_compute_embedding_success_with_api_key(self, mock_truncate, mock_create):
        """Test successful embedding computation with explicit API key."""
        # Setup mocks
        mock_truncate.return_value = "truncated data"
        mock_create.return_value = [0.1, 0.2, 0.3]

        # Call function with api_key
        result = compute_embedding("test data", api_key="test-api-key")

        # Verify
        self.assertEqual(result, [0.1, 0.2, 0.3])
        mock_truncate.assert_called_once_with(
            data="test data",
            encoding_name=settings.ASK_EMBEDDINGS_DEFAULT_ENCODING,
            max_tokens=settings.ASK_EMBEDDINGS_DEFAULT_MAX_INPUT,
        )
        mock_create.assert_called_once_with(
            input_data="truncated data",
            model=settings.ASK_EMBEDDINGS_DEFAULT_MODEL,
            api_key="test-api-key",
            user=None,
        )

    @patch("ask.helpers.embeddings.create_embedding")
    @patch("ask.helpers.embeddings.truncate_input_data")
    def test_compute_embedding_with_custom_params(self, mock_truncate, mock_create):
        """Test embedding computation with custom parameters."""
        # Setup mocks
        mock_truncate.return_value = "truncated data"
        mock_create.return_value = [0.4, 0.5, 0.6]

        # Call function with custom params
        result = compute_embedding(
            data="test data",
            api_key="custom-key",
            model="custom-model",
            encoding_name="custom-encoding",
            max_tokens=1000,
        )

        # Verify
        self.assertEqual(result, [0.4, 0.5, 0.6])
        mock_truncate.assert_called_once_with(
            data="test data",
            encoding_name="custom-encoding",
            max_tokens=1000,
        )
        mock_create.assert_called_once_with(
            input_data="truncated data",
            model="custom-model",
            api_key="custom-key",
            user=None,
        )

    @patch("ask.helpers.embeddings.create_embedding")
    @patch("ask.helpers.embeddings.truncate_input_data")
    def test_compute_embedding_handles_error_silently(self, mock_truncate, mock_create):
        """Test that compute_embedding handles errors silently by default."""
        # Setup mocks to raise an error
        mock_truncate.return_value = "truncated data"
        mock_create.side_effect = Exception("API Error")

        # Call function (should not raise)
        result = compute_embedding("test data", api_key="test-key")

        # Verify returns None on error
        self.assertIsNone(result)

    @patch("ask.helpers.embeddings.create_embedding")
    @patch("ask.helpers.embeddings.truncate_input_data")
    def test_compute_embedding_raises_error_when_requested(self, mock_truncate, mock_create):
        """Test that compute_embedding raises errors when raise_exception=True."""
        # Setup mocks to raise an error
        mock_truncate.return_value = "truncated data"
        mock_create.side_effect = Exception("API Error")

        # Call function with raise_exception=True
        with self.assertRaises(Exception) as context:
            compute_embedding("test data", api_key="test-key", raise_exception=True)

        # Verify correct exception was raised
        self.assertEqual(str(context.exception), "API Error")

    @patch("ask.helpers.embeddings.create_embedding")
    @patch("ask.helpers.embeddings.truncate_input_data")
    def test_compute_embedding_uses_default_model_settings(self, mock_truncate, mock_create):
        """Test that compute_embedding uses default model settings when not provided."""
        # Setup mocks
        mock_truncate.return_value = "truncated data"
        mock_create.return_value = [0.1, 0.2, 0.3]

        # Call function with just api_key
        compute_embedding("test data", api_key="test-key")

        # Verify defaults were used
        mock_truncate.assert_called_once_with(
            data="test data",
            encoding_name=settings.ASK_EMBEDDINGS_DEFAULT_ENCODING,
            max_tokens=settings.ASK_EMBEDDINGS_DEFAULT_MAX_INPUT,
        )
        mock_create.assert_called_once_with(
            input_data="truncated data",
            model=settings.ASK_EMBEDDINGS_DEFAULT_MODEL,
            api_key="test-key",
            user=None,
        )

    @patch("ask.helpers.embeddings.create_embedding")
    @patch("ask.helpers.embeddings.truncate_input_data")
    def test_compute_embedding_truncates_long_input(self, mock_truncate, mock_create):
        """Test that compute_embedding truncates long input data."""
        # Setup mocks
        long_data = "x" * 10000
        mock_truncate.return_value = "truncated"
        mock_create.return_value = [0.1, 0.2, 0.3]

        # Call function
        result = compute_embedding(long_data, api_key="test-key")

        # Verify truncation was called
        mock_truncate.assert_called_once()
        # Verify embedding was created with truncated data
        mock_create.assert_called_once_with(
            input_data="truncated",
            model=settings.ASK_EMBEDDINGS_DEFAULT_MODEL,
            api_key="test-key",
            user=None,
        )
        self.assertEqual(result, [0.1, 0.2, 0.3])

    @patch("ask.helpers.embeddings.create_embedding")
    @patch("ask.helpers.embeddings.truncate_input_data")
    def test_compute_embedding_empty_string(self, mock_truncate, mock_create):
        """Test that compute_embedding handles empty strings."""
        # Setup mocks
        mock_truncate.return_value = ""
        mock_create.return_value = [0.0, 0.0, 0.0]

        # Call function
        result = compute_embedding("", api_key="test-key")

        # Verify
        self.assertEqual(result, [0.0, 0.0, 0.0])
        mock_truncate.assert_called_once_with(
            data="",
            encoding_name=settings.ASK_EMBEDDINGS_DEFAULT_ENCODING,
            max_tokens=settings.ASK_EMBEDDINGS_DEFAULT_MAX_INPUT,
        )

"""
Tests for ask.helpers.llm module.
"""

from unittest.mock import Mock, patch

from django.conf import settings
from django.test import TestCase, override_settings

from ask.helpers.llm import create_chat_completion


@override_settings(
    OPENAI_DEFAULT_CHAT_MODEL="gpt-4",
    OPENAI_DEFAULT_CHAT_MAX_TOKENS=500,
    OPENAI_DEFAULT_CHAT_TEMPERATURE=0.7,
)
class TestCreateChatCompletion(TestCase):
    """Test the create_chat_completion function."""

    @patch("ask.helpers.llm.litellm.completion")
    def test_create_chat_completion_with_api_key(self, mock_completion):
        """Test creating a chat completion with explicit API key."""
        # Setup mock response
        mock_response = Mock()
        mock_response.to_dict.return_value = {
            "id": "chatcmpl-123",
            "choices": [{"message": {"content": "Test response"}}],
        }
        mock_completion.return_value = mock_response

        # Call function with api_key
        messages = [{"role": "user", "content": "Hello"}]
        result = create_chat_completion(messages, api_key="test-api-key")

        # Verify result
        self.assertEqual(result["id"], "chatcmpl-123")
        self.assertEqual(result["choices"][0]["message"]["content"], "Test response")

        # Verify litellm.completion was called with correct arguments
        mock_completion.assert_called_once_with(
            model="gpt-4",
            messages=messages,
            max_tokens=500,
            temperature=0.7,
            api_key="test-api-key",
        )

    @patch("ask.helpers.llm.litellm.completion")
    def test_create_chat_completion_with_custom_model(self, mock_completion):
        """Test creating a chat completion with a custom model."""
        # Setup mock response
        mock_response = Mock()
        mock_response.to_dict.return_value = {"id": "chatcmpl-456"}
        mock_completion.return_value = mock_response

        # Call function with custom model
        messages = [{"role": "user", "content": "Test"}]
        result = create_chat_completion(messages, model="gpt-3.5-turbo", api_key="test-api-key")

        # Verify litellm.completion was called with custom model
        mock_completion.assert_called_once_with(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=500,
            temperature=0.7,
            api_key="test-api-key",
        )

    @patch("ask.helpers.llm.litellm.completion")
    def test_create_chat_completion_with_custom_max_tokens(self, mock_completion):
        """Test creating a chat completion with custom max_tokens."""
        # Setup mock response
        mock_response = Mock()
        mock_response.to_dict.return_value = {"id": "chatcmpl-789"}
        mock_completion.return_value = mock_response

        # Call function with custom max_tokens
        messages = [{"role": "user", "content": "Test"}]
        result = create_chat_completion(messages, max_tokens=1000, api_key="test-api-key")

        # Verify litellm.completion was called with custom max_tokens
        mock_completion.assert_called_once_with(
            model="gpt-4",
            messages=messages,
            max_tokens=1000,
            temperature=0.7,
            api_key="test-api-key",
        )

    @patch("ask.helpers.llm.litellm.completion")
    def test_create_chat_completion_with_custom_temperature(self, mock_completion):
        """Test creating a chat completion with custom temperature."""
        # Setup mock response
        mock_response = Mock()
        mock_response.to_dict.return_value = {"id": "chatcmpl-abc"}
        mock_completion.return_value = mock_response

        # Call function with custom temperature
        messages = [{"role": "user", "content": "Test"}]
        result = create_chat_completion(messages, temperature=0.3, api_key="test-api-key")

        # Verify litellm.completion was called with custom temperature
        mock_completion.assert_called_once_with(
            model="gpt-4",
            messages=messages,
            max_tokens=500,
            temperature=0.3,
            api_key="test-api-key",
        )

    @patch("ask.helpers.llm.litellm.completion")
    def test_create_chat_completion_with_all_custom_params(self, mock_completion):
        """Test creating a chat completion with all custom parameters."""
        # Setup mock response
        mock_response = Mock()
        mock_response.to_dict.return_value = {"id": "chatcmpl-xyz"}
        mock_completion.return_value = mock_response

        # Call function with all custom parameters
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]
        result = create_chat_completion(
            messages,
            model="gpt-3.5-turbo",
            max_tokens=2000,
            temperature=0.9,
            api_key="another-key",
        )

        # Verify litellm.completion was called with all custom parameters
        mock_completion.assert_called_once_with(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=2000,
            temperature=0.9,
            api_key="another-key",
        )

    @patch("ask.helpers.llm.litellm.completion")
    def test_create_chat_completion_with_multiple_messages(self, mock_completion):
        """Test creating a chat completion with multiple messages."""
        # Setup mock response
        mock_response = Mock()
        mock_response.to_dict.return_value = {
            "id": "chatcmpl-multi",
            "choices": [{"message": {"content": "Multi-turn response"}}],
        }
        mock_completion.return_value = mock_response

        # Call function with multiple messages
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language."},
            {"role": "user", "content": "Tell me more."},
        ]
        result = create_chat_completion(messages, api_key="test-api-key")

        # Verify litellm.completion was called with the message list
        mock_completion.assert_called_once_with(
            model="gpt-4",
            messages=messages,
            max_tokens=500,
            temperature=0.7,
            api_key="test-api-key",
        )
        self.assertEqual(result["choices"][0]["message"]["content"], "Multi-turn response")

    @patch("ask.helpers.llm.litellm.completion")
    def test_create_chat_completion_with_zero_temperature(self, mock_completion):
        """Test creating a chat completion with temperature=0 (deterministic)."""
        # Setup mock response
        mock_response = Mock()
        mock_response.to_dict.return_value = {"id": "chatcmpl-zero"}
        mock_completion.return_value = mock_response

        # Call function with temperature=0
        messages = [{"role": "user", "content": "Test"}]
        result = create_chat_completion(messages, temperature=0, api_key="test-api-key")

        # Verify temperature=0 is passed (not treated as None/default)
        mock_completion.assert_called_once_with(
            model="gpt-4",
            messages=messages,
            max_tokens=500,
            temperature=0,
            api_key="test-api-key",
        )

    @patch("ask.helpers.llm.litellm.completion")
    def test_create_chat_completion_response_conversion(self, mock_completion):
        """Test that the response is converted to dict via to_dict()."""
        # Setup mock response with complex structure
        mock_response = Mock()
        expected_dict = {
            "id": "chatcmpl-complex",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Response text"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }
        mock_response.to_dict.return_value = expected_dict
        mock_completion.return_value = mock_response

        # Call function
        messages = [{"role": "user", "content": "Test"}]
        result = create_chat_completion(messages, api_key="test-api-key")

        # Verify to_dict() was called
        mock_response.to_dict.assert_called_once()

        # Verify the result matches the dict
        self.assertEqual(result, expected_dict)
        self.assertEqual(result["id"], "chatcmpl-complex")
        self.assertEqual(result["usage"]["total_tokens"], 30)

    @patch("ask.helpers.llm.litellm.completion")
    def test_create_chat_completion_gpt5_excludes_temperature(self, mock_completion):
        """Test that GPT-5 models exclude temperature parameter."""
        # Setup mock response
        mock_response = Mock()
        mock_response.to_dict.return_value = {"id": "chatcmpl-gpt5"}
        mock_completion.return_value = mock_response

        # Call function with gpt-5 model (should exclude temperature)
        messages = [{"role": "user", "content": "Test"}]
        result = create_chat_completion(messages, model="gpt-5-turbo", api_key="test-api-key")

        # Verify litellm.completion was called WITHOUT temperature parameter
        mock_completion.assert_called_once_with(
            model="gpt-5-turbo",
            messages=messages,
            max_tokens=500,
            api_key="test-api-key",
        )

    @patch("ask.helpers.llm.litellm.completion")
    def test_create_chat_completion_gpt5_custom_temperature_excluded(self, mock_completion):
        """Test that GPT-5 models exclude temperature even when custom temperature is provided."""
        # Setup mock response
        mock_response = Mock()
        mock_response.to_dict.return_value = {"id": "chatcmpl-gpt5-custom"}
        mock_completion.return_value = mock_response

        # Call function with gpt-5 model and custom temperature
        # Custom temperature should be ignored
        messages = [{"role": "user", "content": "Test"}]
        result = create_chat_completion(messages, model="gpt-5-preview", temperature=0.8, api_key="test-api-key")

        # Verify litellm.completion was called WITHOUT temperature parameter
        mock_completion.assert_called_once_with(
            model="gpt-5-preview",
            messages=messages,
            max_tokens=500,
            api_key="test-api-key",
        )

    @patch("ask.helpers.llm.litellm.completion")
    def test_create_chat_completion_gpt5_zero_temperature_excluded(self, mock_completion):
        """Test that GPT-5 models exclude temperature even when temperature=0."""
        # Setup mock response
        mock_response = Mock()
        mock_response.to_dict.return_value = {"id": "chatcmpl-gpt5-zero"}
        mock_completion.return_value = mock_response

        # Call function with gpt-5 model and temperature=0
        messages = [{"role": "user", "content": "Test"}]
        result = create_chat_completion(messages, model="gpt-5", temperature=0, api_key="test-api-key")

        # Verify litellm.completion was called WITHOUT temperature parameter
        mock_completion.assert_called_once_with(
            model="gpt-5",
            messages=messages,
            max_tokens=500,
            api_key="test-api-key",
        )

    @patch("ask.helpers.llm.litellm.completion")
    def test_create_chat_completion_non_gpt5_includes_temperature(self, mock_completion):
        """Test that non-GPT-5 models (GPT-4, GPT-3.5) include temperature parameter."""
        # Setup mock response
        mock_response = Mock()
        mock_response.to_dict.return_value = {"id": "chatcmpl-gpt4"}
        mock_completion.return_value = mock_response

        # Test various non-GPT-5 models
        test_models = ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4o"]

        for model in test_models:
            mock_completion.reset_mock()

            messages = [{"role": "user", "content": "Test"}]
            result = create_chat_completion(messages, model=model, temperature=0.5, api_key="test-api-key")

            # Verify litellm.completion was called WITH temperature parameter
            mock_completion.assert_called_once_with(
                model=model,
                messages=messages,
                max_tokens=500,
                temperature=0.5,
                api_key="test-api-key",
            )

    @patch("ask.helpers.llm.litellm.completion")
    def test_create_chat_completion_gpt5_variants(self, mock_completion):
        """Test that all GPT-5 model variants exclude temperature."""
        # Setup mock response
        mock_response = Mock()
        mock_response.to_dict.return_value = {"id": "chatcmpl-gpt5-variant"}
        mock_completion.return_value = mock_response

        # Test various GPT-5 model names
        gpt5_models = ["gpt-5", "gpt-5-turbo", "gpt-5-preview", "gpt-5-custom"]

        for model in gpt5_models:
            mock_completion.reset_mock()

            messages = [{"role": "user", "content": "Test"}]
            result = create_chat_completion(messages, model=model, api_key="test-api-key")

            # Verify litellm.completion was called WITHOUT temperature parameter
            mock_completion.assert_called_once()
            call_kwargs = mock_completion.call_args[1]
            self.assertNotIn("temperature", call_kwargs, f"Model {model} should not include temperature")
            self.assertEqual(call_kwargs["model"], model)

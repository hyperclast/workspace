"""
Unit tests for AI edit generation helpers.

Covers:
- _extract_context_window: context windowing around anchor text
- generate_edit_from_comment: LLM call orchestration
"""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from pages.tasks import EDIT_SYSTEM_PROMPT, _extract_context_window, generate_edit_from_comment
from pages.tests.factories import CommentFactory, PageFactory, ProjectFactory
from users.tests.factories import UserFactory


class TestExtractContextWindow(SimpleTestCase):
    """Tests for _extract_context_window — a pure function that extracts
    lines surrounding the anchor text for LLM context."""

    def _make_doc(self, num_lines):
        """Create a document with numbered lines."""
        return "\n".join(f"Line {i}" for i in range(num_lines))

    def test_anchor_in_middle_returns_surrounding_lines(self):
        doc = self._make_doc(200)
        anchor = "Line 100"
        result = _extract_context_window(doc, anchor, context_lines=5)
        lines = result.split("\n")
        # 5 lines before line 100, line 100 itself, 5 lines after = 11
        self.assertEqual(len(lines), 11)
        self.assertIn("Line 95", lines[0])
        self.assertIn("Line 100", result)
        self.assertIn("Line 105", lines[-1])

    def test_anchor_near_start_clamps_to_zero(self):
        doc = self._make_doc(100)
        anchor = "Line 2"
        result = _extract_context_window(doc, anchor, context_lines=10)
        lines = result.split("\n")
        # Should start from line 0, not go negative
        self.assertEqual(lines[0], "Line 0")
        self.assertIn("Line 2", result)

    def test_anchor_near_end_clamps_to_doc_length(self):
        doc = self._make_doc(100)
        anchor = "Line 98"
        result = _extract_context_window(doc, anchor, context_lines=10)
        lines = result.split("\n")
        # Should end at line 99 (last line), not exceed
        self.assertEqual(lines[-1], "Line 99")
        self.assertIn("Line 98", result)

    def test_anchor_not_found_returns_full_content_when_short(self):
        doc = "Short document with a few lines.\nSecond line.\nThird line."
        result = _extract_context_window(doc, "nonexistent text")
        self.assertEqual(result, doc)

    def test_anchor_not_found_truncates_large_document(self):
        """When anchor is not found in a large doc, truncate to MAX_CHARS_PER_PAGE."""
        from pages.tasks import MAX_CHARS_PER_PAGE

        # Create a document larger than MAX_CHARS_PER_PAGE
        doc = "x" * (MAX_CHARS_PER_PAGE + 5000)
        result = _extract_context_window(doc, "nonexistent text")
        self.assertEqual(len(result), MAX_CHARS_PER_PAGE)
        self.assertEqual(result, doc[:MAX_CHARS_PER_PAGE])

    def test_small_document_returns_everything(self):
        doc = "Line A\nLine B\nLine C"
        result = _extract_context_window(doc, "Line B", context_lines=50)
        self.assertEqual(result, doc)

    def test_single_line_document(self):
        doc = "The only line in the document."
        result = _extract_context_window(doc, "only line", context_lines=50)
        self.assertEqual(result, doc)

    def test_empty_document(self):
        result = _extract_context_window("", "anything")
        self.assertEqual(result, "")

    def test_anchor_on_first_line(self):
        doc = self._make_doc(100)
        anchor = "Line 0"
        result = _extract_context_window(doc, anchor, context_lines=5)
        lines = result.split("\n")
        self.assertEqual(lines[0], "Line 0")
        # Should include lines 0-5 (6 lines)
        self.assertEqual(len(lines), 6)

    def test_anchor_on_last_line(self):
        doc = self._make_doc(100)
        anchor = "Line 99"
        result = _extract_context_window(doc, anchor, context_lines=5)
        lines = result.split("\n")
        self.assertEqual(lines[-1], "Line 99")
        # Should include lines 94-99 (6 lines)
        self.assertEqual(len(lines), 6)

    def test_context_lines_zero_returns_just_anchor_line(self):
        doc = self._make_doc(100)
        result = _extract_context_window(doc, "Line 50", context_lines=0)
        self.assertEqual(result, "Line 50")

    def test_anchor_spanning_partial_line(self):
        doc = "First line has some words.\nSecond line has more words.\nThird line ends here."
        # Anchor is a substring of the second line
        result = _extract_context_window(doc, "has more", context_lines=1)
        lines = result.split("\n")
        self.assertEqual(len(lines), 3)
        self.assertIn("First line", lines[0])
        self.assertIn("has more", lines[1])
        self.assertIn("Third line", lines[2])

    def test_duplicate_anchor_uses_first_occurrence(self):
        doc = "foo bar\nfoo bar\nfoo bar"
        result = _extract_context_window(doc, "foo bar", context_lines=0)
        # First occurrence is on line 0
        self.assertEqual(result, "foo bar")

    def test_default_context_lines_is_50(self):
        doc = self._make_doc(200)
        result = _extract_context_window(doc, "Line 100")
        lines = result.split("\n")
        # 50 before + anchor line + 50 after = 101
        self.assertEqual(len(lines), 101)
        self.assertEqual(lines[0], "Line 50")
        self.assertEqual(lines[-1], "Line 150")

    def test_multiline_anchor_text(self):
        doc = "Line A\nLine B\nLine C\nLine D\nLine E"
        # Anchor spans lines B and C
        anchor = "Line B\nLine C"
        result = _extract_context_window(doc, anchor, context_lines=1)
        lines = result.split("\n")
        # Anchor starts on line 1 (Line B), so window is lines 0-2
        self.assertEqual(lines[0], "Line A")
        self.assertIn("Line B", result)
        self.assertEqual(lines[-1], "Line C")


@patch("pages.tasks.create_chat_completion")
@patch("pages.tasks.get_ai_config_for_user")
class TestGenerateEditFromComment(TestCase):
    """Tests for generate_edit_from_comment — LLM call orchestration."""

    def setUp(self):
        self.user = UserFactory()
        self.project = ProjectFactory(creator=self.user)
        self.page = PageFactory(
            project=self.project,
            creator=self.user,
            title="My Document",
            details={"content": "First paragraph.\n\nSecond paragraph about testing.\n\nThird paragraph."},
        )
        self.comment = CommentFactory(
            page=self.page,
            author=None,
            ai_persona="dewey",
            anchor_text="Second paragraph about testing.",
            requester=self.user,
            body="You should add a reference to Smith et al. (2024) here.",
        )

    def _mock_llm_response(self, text):
        return {"choices": [{"message": {"content": text}}]}

    def test_returns_llm_response_text(self, mock_config, mock_completion):
        mock_config.return_value = MagicMock(model_name="custom-model", provider="openai")
        mock_completion.return_value = self._mock_llm_response("See Smith et al. (2024) for details.")

        result = generate_edit_from_comment(self.comment, self.page, self.user)
        self.assertEqual(result, "See Smith et al. (2024) for details.")

    def test_strips_whitespace_from_response(self, mock_config, mock_completion):
        mock_config.return_value = MagicMock(model_name="custom-model", provider="openai")
        mock_completion.return_value = self._mock_llm_response("  Some text with whitespace  \n\n")

        result = generate_edit_from_comment(self.comment, self.page, self.user)
        self.assertEqual(result, "Some text with whitespace")

    def test_passes_system_prompt(self, mock_config, mock_completion):
        mock_config.return_value = MagicMock(model_name="custom-model", provider="openai")
        mock_completion.return_value = self._mock_llm_response("response")

        generate_edit_from_comment(self.comment, self.page, self.user)

        call_kwargs = mock_completion.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], EDIT_SYSTEM_PROMPT)

    def test_user_content_includes_anchor_text(self, mock_config, mock_completion):
        mock_config.return_value = MagicMock(model_name="custom-model", provider="openai")
        mock_completion.return_value = self._mock_llm_response("response")

        generate_edit_from_comment(self.comment, self.page, self.user)

        call_kwargs = mock_completion.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        user_msg = messages[1]["content"]
        self.assertIn("Second paragraph about testing.", user_msg)

    def test_user_content_includes_page_title(self, mock_config, mock_completion):
        mock_config.return_value = MagicMock(model_name="custom-model", provider="openai")
        mock_completion.return_value = self._mock_llm_response("response")

        generate_edit_from_comment(self.comment, self.page, self.user)

        call_kwargs = mock_completion.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        user_msg = messages[1]["content"]
        self.assertIn("My Document", user_msg)

    def test_includes_thread_context_in_prompt(self, mock_config, mock_completion):
        """The comment body should appear in the LLM prompt as thread context."""
        mock_config.return_value = MagicMock(model_name="custom-model", provider="openai")
        mock_completion.return_value = self._mock_llm_response("response")

        generate_edit_from_comment(self.comment, self.page, self.user)

        call_kwargs = mock_completion.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        user_msg = messages[1]["content"]
        self.assertIn("Smith et al.", user_msg)

    def test_uses_review_model_fallback_when_no_custom_model(self, mock_config, mock_completion):
        """When user has no custom model name, uses REVIEW_MODELS fallback."""
        from ask.constants import AIProvider

        mock_config.return_value = MagicMock(model_name="", provider=AIProvider.OPENAI.value)
        mock_completion.return_value = self._mock_llm_response("response")

        generate_edit_from_comment(self.comment, self.page, self.user)

        call_kwargs = mock_completion.call_args
        model = call_kwargs.kwargs.get("model") or call_kwargs[1].get("model")
        self.assertIsNotNone(model)

    def test_handles_ai_key_not_configured(self, mock_config, mock_completion):
        """AIKeyNotConfiguredError propagates to the caller (API layer returns 400)."""
        from ask.exceptions import AIKeyNotConfiguredError

        mock_config.side_effect = AIKeyNotConfiguredError()

        with self.assertRaises(AIKeyNotConfiguredError):
            generate_edit_from_comment(self.comment, self.page, self.user)

        mock_completion.assert_not_called()

    def test_llm_exception_propagates(self, mock_config, mock_completion):
        """LLM errors should propagate to the caller (API layer handles them)."""
        mock_config.return_value = MagicMock(model_name="custom-model", provider="openai")
        mock_completion.side_effect = Exception("LLM unavailable")

        with self.assertRaises(Exception, msg="LLM unavailable"):
            generate_edit_from_comment(self.comment, self.page, self.user)

    def test_empty_page_content(self, mock_config, mock_completion):
        """Works with empty page content (anchor won't be found, falls back)."""
        mock_config.return_value = MagicMock(model_name="custom-model", provider="openai")
        mock_completion.return_value = self._mock_llm_response("response")

        self.page.details = {"content": ""}
        self.page.save(update_fields=["details"])

        result = generate_edit_from_comment(self.comment, self.page, self.user)
        self.assertEqual(result, "response")

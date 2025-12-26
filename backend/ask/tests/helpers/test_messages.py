"""
Tests for ask.helpers.messages module.
"""

from django.test import TestCase

from ask.helpers.messages import build_ask_request_messages
from pages.tests.factories import PageFactory


class TestBuildAskRequestMessages(TestCase):
    """Test the build_ask_request_messages function."""

    def test_build_ask_request_messages_with_single_page(self):
        """Test building messages with a single page."""
        page = PageFactory(title="Meeting Pages", details={"content": "Discussed project timeline"})

        question = "What did we discuss?"
        messages = build_ask_request_messages(question, [page])

        # Should return 3 messages: system, assistant, user
        self.assertEqual(len(messages), 3)

        # Verify system message
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("assistant that helps users answer questions", messages[0]["content"])

        # Verify assistant message contains page content
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertIn("Meeting Pages", messages[1]["content"])
        self.assertIn("Discussed project timeline", messages[1]["content"])
        self.assertIn("[title]:", messages[1]["content"])
        self.assertIn("[content]:", messages[1]["content"])

        # Verify user message
        self.assertEqual(messages[2]["role"], "user")
        self.assertEqual(messages[2]["content"], question)

    def test_build_ask_request_messages_with_multiple_pages(self):
        """Test building messages with multiple pages."""
        page1 = PageFactory(title="Meeting Pages", details={"content": "Project timeline discussion"})
        page2 = PageFactory(title="Budget Review", details={"content": "Q4 budget planning"})
        page3 = PageFactory(title="Action Items", details={"content": "Follow up with team"})

        question = "What are the main topics?"
        messages = build_ask_request_messages(question, [page1, page2, page3])

        # Verify structure
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[2]["role"], "user")

        # Verify all pages are included in assistant message
        assistant_content = messages[1]["content"]
        self.assertIn("Meeting Pages", assistant_content)
        self.assertIn("Budget Review", assistant_content)
        self.assertIn("Action Items", assistant_content)
        self.assertIn("Project timeline discussion", assistant_content)
        self.assertIn("Q4 budget planning", assistant_content)
        self.assertIn("Follow up with team", assistant_content)

        # Verify separator between pages
        self.assertIn("---", assistant_content)

    def test_build_ask_request_messages_with_page_without_content(self):
        """Test building messages with a page that has no content."""
        # Page with title but no content in details
        page = PageFactory(title="Empty Page", details={})

        question = "What's in this page?"
        messages = build_ask_request_messages(question, [page])

        self.assertEqual(len(messages), 3)

        # Assistant message should include title but not [content] section
        assistant_content = messages[1]["content"]
        self.assertIn("Empty Page", assistant_content)
        self.assertIn("[title]:", assistant_content)
        # Should NOT include [content]: section since details has no content key
        self.assertEqual(assistant_content.count("[content]:"), 0)

    def test_build_ask_request_messages_with_page_with_empty_content(self):
        """Test building messages with a page that has empty string content."""
        # Page with empty string content (falsy value)
        page = PageFactory(title="Page with Empty Content", details={"content": ""})

        question = "What's here?"
        messages = build_ask_request_messages(question, [page])

        # Assistant message should include title but not [content] section
        # because empty string is falsy in template
        assistant_content = messages[1]["content"]
        self.assertIn("Page with Empty Content", assistant_content)
        self.assertIn("[title]:", assistant_content)
        # Should NOT include [content]: section since content is empty string (falsy)
        self.assertEqual(assistant_content.count("[content]:"), 0)

    def test_build_ask_request_messages_with_mixed_pages(self):
        """Test building messages with mix of pages with and without content."""
        page1 = PageFactory(title="Page with Content", details={"content": "Some content here"})
        page2 = PageFactory(title="Page without Content", details={})
        page3 = PageFactory(title="Page with Empty Content", details={"content": ""})

        question = "Summarize these pages"
        messages = build_ask_request_messages(question, [page1, page2, page3])

        assistant_content = messages[1]["content"]

        # All titles should be present
        self.assertIn("Page with Content", assistant_content)
        self.assertIn("Page without Content", assistant_content)
        self.assertIn("Page with Empty Content", assistant_content)

        # Only page1 should have [content]: section
        self.assertIn("Some content here", assistant_content)
        # Should have exactly one [content]: section
        self.assertEqual(assistant_content.count("[content]:"), 1)

    def test_build_ask_request_messages_with_long_content(self):
        """Test that long content is truncated to 3000 characters."""
        # Create content longer than 3000 characters
        long_content = "A" * 4000

        page = PageFactory(title="Long Page", details={"content": long_content})

        question = "What's in this long page?"
        messages = build_ask_request_messages(question, [page])

        assistant_content = messages[1]["content"]

        # Content should be truncated
        # truncatechars:3000 truncates to 3000 chars including the "..." suffix
        self.assertIn("Long Page", assistant_content)
        # Should not contain the full 4000 A's
        self.assertLess(len(assistant_content), 4100)
        # Should contain some A's but truncated
        self.assertIn("A" * 100, assistant_content)  # At least some As present

    def test_build_ask_request_messages_with_empty_pages_list(self):
        """Test building messages with empty pages list."""
        question = "What are my pages about?"
        messages = build_ask_request_messages(question, [])

        # Should still return 3 messages
        self.assertEqual(len(messages), 3)

        # Assistant message should still have the header but no pages
        assistant_content = messages[1]["content"]
        self.assertIn("Here are the most relevant pages", assistant_content)
        # Should not have any [title]: sections
        self.assertEqual(assistant_content.count("[title]:"), 0)

    def test_build_ask_request_messages_question_is_preserved(self):
        """Test that the question is preserved exactly in user message."""
        page = PageFactory(title="Test Page", details={"content": "Test content"})

        question = "This is a very specific question with special chars: @#$%?"
        messages = build_ask_request_messages(question, [page])

        # User message should have exact question
        self.assertEqual(messages[2]["content"], question)

    def test_build_ask_request_messages_page_with_special_characters(self):
        """Test building messages with page containing special characters."""
        page = PageFactory(
            title="Page with Special Chars: @#$%",
            details={"content": "Content with <html> & special\ncharacters\ttabs"},
        )

        question = "What's here?"
        messages = build_ask_request_messages(question, [page])

        assistant_content = messages[1]["content"]

        # Django templates auto-escape HTML special characters even in .txt files
        self.assertIn("Page with Special Chars: @#$%", assistant_content)
        self.assertIn("Content with &lt;html&gt; &amp; special", assistant_content)
        # Newlines and tabs should be preserved
        self.assertIn("characters\ttabs", assistant_content)

    def test_build_ask_request_messages_page_with_unicode(self):
        """Test building messages with page containing unicode characters."""
        page = PageFactory(
            title="Unicode Page: 你好 🎉",
            details={"content": "Content with émojis 😀 and àccénts"},
        )

        question = "What's in this page?"
        messages = build_ask_request_messages(question, [page])

        assistant_content = messages[1]["content"]

        # Unicode should be preserved
        self.assertIn("Unicode Page: 你好 🎉", assistant_content)
        self.assertIn("Content with émojis 😀 and àccénts", assistant_content)

    def test_build_ask_request_messages_system_message_content(self):
        """Test that system message has correct content."""
        page = PageFactory(title="Test", details={"content": "Test"})

        messages = build_ask_request_messages("Test question", [page])

        system_message = messages[0]
        self.assertEqual(system_message["role"], "system")
        self.assertEqual(
            system_message["content"],
            "You are an assistant that helps users answer questions and gather information from their pages.",
        )

    def test_build_ask_request_messages_format_structure(self):
        """Test that the assistant message has correct format structure."""
        page = PageFactory(title="Test Page", details={"content": "Test content"})

        messages = build_ask_request_messages("Test?", [page])

        assistant_content = messages[1]["content"]

        # Verify format structure
        self.assertIn("Here are the most relevant pages", assistant_content)
        self.assertIn("[title]:", assistant_content)
        self.assertIn("[content]:", assistant_content)
        self.assertIn("---", assistant_content)

    def test_build_ask_request_messages_order_preserved(self):
        """Test that pages appear in the same order as provided."""
        page1 = PageFactory(title="First Page", details={"content": "First"})
        page2 = PageFactory(title="Second Page", details={"content": "Second"})
        page3 = PageFactory(title="Third Page", details={"content": "Third"})

        messages = build_ask_request_messages("Test?", [page1, page2, page3])

        assistant_content = messages[1]["content"]

        # Find positions of titles
        first_pos = assistant_content.find("First Page")
        second_pos = assistant_content.find("Second Page")
        third_pos = assistant_content.find("Third Page")

        # Verify order is preserved
        self.assertLess(first_pos, second_pos)
        self.assertLess(second_pos, third_pos)

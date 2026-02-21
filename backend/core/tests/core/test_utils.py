from django.test import SimpleTestCase

from core.utils import (
    FILETYPE_CONTENT_TYPES,
    get_content_type_for_filetype,
    prepare_page_content_for_export,
    sanitize_filename,
)


class TestSanitizeFilename(SimpleTestCase):
    """Unit tests for the sanitize_filename utility function."""

    # ========================================
    # Basic Functionality Tests
    # ========================================

    def test_simple_title(self):
        """Test that a simple title is preserved."""
        self.assertEqual(sanitize_filename("My Document"), "My-Document")

    def test_title_with_single_space(self):
        """Test that single spaces are converted to dashes."""
        self.assertEqual(sanitize_filename("Hello World"), "Hello-World")

    # ========================================
    # Invalid Character Replacement Tests
    # ========================================

    def test_forward_slash_replaced(self):
        """Test that forward slash is replaced with dash."""
        self.assertEqual(sanitize_filename("File/Name"), "File-Name")

    def test_backslash_replaced(self):
        """Test that backslash is replaced with dash."""
        self.assertEqual(sanitize_filename("File\\Name"), "File-Name")

    def test_colon_replaced(self):
        """Test that colon is replaced with dash."""
        self.assertEqual(sanitize_filename("File:Name"), "File-Name")

    def test_asterisk_replaced(self):
        """Test that asterisk is replaced with dash."""
        self.assertEqual(sanitize_filename("File*Name"), "File-Name")

    def test_question_mark_replaced(self):
        """Test that question mark is replaced with dash."""
        self.assertEqual(sanitize_filename("File?Name"), "File-Name")

    def test_double_quote_replaced(self):
        """Test that double quote is replaced with dash."""
        self.assertEqual(sanitize_filename('File"Name'), "File-Name")

    def test_less_than_replaced(self):
        """Test that less-than sign is replaced with dash."""
        self.assertEqual(sanitize_filename("File<Name"), "File-Name")

    def test_greater_than_replaced(self):
        """Test that greater-than sign is replaced with dash."""
        self.assertEqual(sanitize_filename("File>Name"), "File-Name")

    def test_pipe_replaced(self):
        """Test that pipe character is replaced with dash."""
        self.assertEqual(sanitize_filename("File|Name"), "File-Name")

    def test_all_invalid_chars_replaced(self):
        """Test that all invalid characters are replaced."""
        # Note: trailing invalid char becomes trailing dash (acceptable behavior)
        self.assertEqual(
            sanitize_filename('File/With\\Special:Chars*?"<>|'),
            "File-With-Special-Chars-",
        )

    # ========================================
    # Whitespace Handling Tests
    # ========================================

    def test_multiple_spaces_collapsed(self):
        """Test that multiple spaces are collapsed to single dash."""
        self.assertEqual(sanitize_filename("File   Name"), "File-Name")

    def test_leading_whitespace_stripped(self):
        """Test that leading whitespace is stripped."""
        self.assertEqual(sanitize_filename("   File"), "File")

    def test_trailing_whitespace_stripped(self):
        """Test that trailing whitespace is stripped."""
        self.assertEqual(sanitize_filename("File   "), "File")

    def test_newlines_replaced(self):
        """Test that newlines are replaced with dashes."""
        self.assertEqual(sanitize_filename("File\nName"), "File-Name")

    def test_tabs_replaced(self):
        """Test that tabs are replaced with dashes."""
        self.assertEqual(sanitize_filename("File\tName"), "File-Name")

    def test_carriage_returns_replaced(self):
        """Test that carriage returns are replaced with dashes."""
        self.assertEqual(sanitize_filename("File\rName"), "File-Name")

    def test_crlf_replaced(self):
        """Test that CRLF sequences are replaced with dashes."""
        self.assertEqual(sanitize_filename("File\r\nName"), "File-Name")

    def test_whitespace_only_returns_untitled(self):
        """Test that whitespace-only input returns Untitled."""
        self.assertEqual(sanitize_filename("   "), "Untitled")

    # ========================================
    # Dot Handling Tests
    # ========================================

    def test_leading_dots_stripped(self):
        """Test that leading dots are stripped."""
        self.assertEqual(sanitize_filename("...File"), "File")

    def test_trailing_dots_stripped(self):
        """Test that trailing dots are stripped."""
        self.assertEqual(sanitize_filename("File..."), "File")

    def test_leading_and_trailing_dots_stripped(self):
        """Test that both leading and trailing dots are stripped."""
        self.assertEqual(sanitize_filename("...File..."), "File")

    def test_dots_in_middle_preserved(self):
        """Test that dots in the middle of the name are preserved."""
        self.assertEqual(sanitize_filename("File.Name"), "File.Name")

    # ========================================
    # Dash Handling Tests
    # ========================================

    def test_multiple_dashes_collapsed(self):
        """Test that multiple dashes are collapsed to single dash."""
        self.assertEqual(sanitize_filename("File---Name"), "File-Name")

    def test_mixed_spaces_and_dashes_collapsed(self):
        """Test that mixed spaces and dashes are collapsed."""
        self.assertEqual(sanitize_filename("File - - - Name"), "File-Name")

    def test_title_starting_with_dash(self):
        """Test that titles starting with dash are handled."""
        # Note: leading dashes are preserved (only dots are stripped)
        self.assertEqual(sanitize_filename("- My Page"), "-My-Page")

    # ========================================
    # Empty/Fallback Tests
    # ========================================

    def test_empty_string_returns_untitled(self):
        """Test that empty string returns Untitled."""
        self.assertEqual(sanitize_filename(""), "Untitled")

    def test_only_invalid_chars_returns_dash(self):
        """Test that input with only invalid chars returns a dash.

        Each invalid char becomes a dash, then multiple dashes are collapsed
        to a single dash. The fallback to 'Untitled' only happens when the
        result is empty, not when it's a single dash.
        """
        self.assertEqual(sanitize_filename("???***"), "-")

    def test_only_dots_returns_untitled(self):
        """Test that input with only dots returns Untitled."""
        self.assertEqual(sanitize_filename("..."), "Untitled")

    # ========================================
    # Unicode Tests
    # ========================================

    def test_unicode_preserved(self):
        """Test that unicode characters are preserved."""
        self.assertEqual(sanitize_filename("日本語タイトル"), "日本語タイトル")

    def test_emoji_preserved(self):
        """Test that emoji characters are preserved."""
        self.assertEqual(sanitize_filename("My Page 🚀"), "My-Page-🚀")

    def test_mixed_unicode_and_invalid_chars(self):
        """Test that invalid chars are replaced while preserving unicode."""
        self.assertEqual(sanitize_filename("日本語/Title"), "日本語-Title")

    # ========================================
    # Security-Related Tests
    # ========================================

    def test_crlf_injection_attempt_neutralized(self):
        """Test that CRLF injection attempts are neutralized."""
        result = sanitize_filename("file.txt\r\nX-Injected-Header: malicious")
        self.assertNotIn("\r\n", result)
        self.assertNotIn("\r", result)
        self.assertNotIn("\n", result)
        self.assertNotIn(":", result)

    def test_header_injection_attempt_neutralized(self):
        """Test that header injection attempts are neutralized."""
        result = sanitize_filename("project.zip\r\nContent-Type: text/html")
        self.assertNotIn("\r\n", result)
        self.assertNotIn(":", result)

    def test_quotes_removed_for_header_safety(self):
        """Test that quotes are removed to prevent header injection."""
        result = sanitize_filename('File"With"Quotes')
        self.assertNotIn('"', result)
        self.assertEqual(result, "File-With-Quotes")


class TestGetContentTypeForFiletype(SimpleTestCase):
    """Unit tests for get_content_type_for_filetype utility function."""

    def test_markdown_content_type(self):
        """Test that markdown files get text/markdown content type."""
        self.assertEqual(get_content_type_for_filetype("md"), "text/markdown")

    def test_csv_content_type(self):
        """Test that CSV files get text/csv content type."""
        self.assertEqual(get_content_type_for_filetype("csv"), "text/csv")

    def test_txt_content_type(self):
        """Test that text files get text/plain content type."""
        self.assertEqual(get_content_type_for_filetype("txt"), "text/plain")

    def test_unknown_filetype_defaults_to_text_plain(self):
        """Test that unknown file types default to text/plain."""
        self.assertEqual(get_content_type_for_filetype("unknown"), "text/plain")
        self.assertEqual(get_content_type_for_filetype(""), "text/plain")
        self.assertEqual(get_content_type_for_filetype("pdf"), "text/plain")

    def test_filetype_content_types_constant(self):
        """Test that the constant contains expected mappings."""
        self.assertEqual(FILETYPE_CONTENT_TYPES["md"], "text/markdown")
        self.assertEqual(FILETYPE_CONTENT_TYPES["csv"], "text/csv")
        self.assertEqual(FILETYPE_CONTENT_TYPES["txt"], "text/plain")
        self.assertEqual(len(FILETYPE_CONTENT_TYPES), 3)


class TestPreparePageContentForExport(SimpleTestCase):
    """Unit tests for prepare_page_content_for_export utility function."""

    def test_markdown_prepends_title_as_h1(self):
        """Test that markdown files get title prepended as H1."""
        result = prepare_page_content_for_export("My Page", "Some content", "md")
        self.assertEqual(result, "# My Page\n\nSome content")

    def test_markdown_empty_content(self):
        """Test markdown with empty content still gets title."""
        result = prepare_page_content_for_export("My Page", "", "md")
        self.assertEqual(result, "# My Page\n\n")

    def test_csv_returns_content_unchanged(self):
        """Test that CSV files return content unchanged."""
        content = "col1,col2\nval1,val2"
        result = prepare_page_content_for_export("My Data", content, "csv")
        self.assertEqual(result, content)

    def test_txt_returns_content_unchanged(self):
        """Test that text files return content unchanged."""
        content = "Plain text content"
        result = prepare_page_content_for_export("My Notes", content, "txt")
        self.assertEqual(result, content)

    def test_unknown_filetype_returns_content_unchanged(self):
        """Test that unknown file types return content unchanged."""
        content = "Some content"
        result = prepare_page_content_for_export("Title", content, "xyz")
        self.assertEqual(result, content)

    def test_empty_filetype_returns_content_unchanged(self):
        """Test that empty filetype returns content unchanged."""
        content = "Some content"
        result = prepare_page_content_for_export("Title", content, "")
        self.assertEqual(result, content)

    def test_markdown_with_special_characters_in_title(self):
        """Test that special characters in title are preserved for markdown."""
        result = prepare_page_content_for_export("My & Page <Title>", "Content", "md")
        self.assertEqual(result, "# My & Page <Title>\n\nContent")

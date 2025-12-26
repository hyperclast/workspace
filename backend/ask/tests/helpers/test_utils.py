"""
Tests for ask.helpers.utils module.
"""

from django.test import TestCase

from ask.helpers.utils import parse_mentions


class TestParseMentions(TestCase):
    """Test the parse_mentions function."""

    def test_parse_mentions_with_single_mention(self):
        """Test parsing a query with a single mention."""
        query = "What is @[Meeting Pages](abc123) about?"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "What is Meeting Pages about?")
        self.assertEqual(page_ids, ["abc123"])

    def test_parse_mentions_with_multiple_mentions(self):
        """Test parsing a query with multiple mentions."""
        query = "Summarize @[Page 1](id1) and @[Page 2](id2)"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "Summarize Page 1 and Page 2")
        self.assertEqual(page_ids, ["id1", "id2"])

    def test_parse_mentions_with_no_mentions(self):
        """Test parsing a query with no mentions."""
        query = "What are my pages about?"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "What are my pages about?")
        self.assertEqual(page_ids, [])

    def test_parse_mentions_with_empty_string(self):
        """Test parsing an empty query."""
        query = ""
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "")
        self.assertEqual(page_ids, [])

    def test_parse_mentions_with_malformed_mention_no_closing_bracket(self):
        """Test that malformed mentions (no closing bracket) are not parsed."""
        query = "What is @[Meeting Pages(abc123) about?"
        cleaned_query, page_ids = parse_mentions(query)

        # Should not match because missing ]
        self.assertEqual(cleaned_query, "What is @[Meeting Pages(abc123) about?")
        self.assertEqual(page_ids, [])

    def test_parse_mentions_with_malformed_mention_no_opening_paren(self):
        """Test that malformed mentions (no opening paren) are not parsed."""
        query = "What is @[Meeting Pages]abc123) about?"
        cleaned_query, page_ids = parse_mentions(query)

        # Should not match because missing (
        self.assertEqual(cleaned_query, "What is @[Meeting Pages]abc123) about?")
        self.assertEqual(page_ids, [])

    def test_parse_mentions_with_special_characters_in_title(self):
        """Test parsing mentions with special characters in the title."""
        query = "Check @[Meeting Pages - Q4 2024!](xyz789)"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "Check Meeting Pages - Q4 2024!")
        self.assertEqual(page_ids, ["xyz789"])

    def test_parse_mentions_with_uuid_page_id(self):
        """Test parsing mentions with UUID-style page IDs."""
        query = "Review @[Project Plan](550e8400-e29b-41d4-a716-446655440000)"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "Review Project Plan")
        self.assertEqual(page_ids, ["550e8400-e29b-41d4-a716-446655440000"])

    def test_parse_mentions_with_consecutive_mentions(self):
        """Test parsing query with consecutive mentions (no space between)."""
        query = "@[Page A](id_a)@[Page B](id_b)"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "Page APage B")
        self.assertEqual(page_ids, ["id_a", "id_b"])

    def test_parse_mentions_with_mention_at_beginning(self):
        """Test parsing query with mention at the beginning."""
        query = "@[Meeting Pages](abc123) was interesting"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "Meeting Pages was interesting")
        self.assertEqual(page_ids, ["abc123"])

    def test_parse_mentions_with_mention_at_end(self):
        """Test parsing query with mention at the end."""
        query = "Please summarize @[Project Plan](def456)"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "Please summarize Project Plan")
        self.assertEqual(page_ids, ["def456"])

    def test_parse_mentions_preserves_order(self):
        """Test that the order of page IDs matches the order in the query."""
        query = "@[Third](3) comes after @[First](1) and @[Second](2)"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "Third comes after First and Second")
        self.assertEqual(page_ids, ["3", "1", "2"])

    def test_parse_mentions_with_duplicate_mentions(self):
        """Test parsing query with the same page mentioned multiple times."""
        query = "Compare @[Page A](same_id) with @[Page A](same_id)"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "Compare Page A with Page A")
        # Both instances should be captured
        self.assertEqual(page_ids, ["same_id", "same_id"])

    def test_parse_mentions_with_numbers_in_title(self):
        """Test parsing mentions with numbers in the title."""
        query = "Review @[Meeting 2024-12-06](page123)"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "Review Meeting 2024-12-06")
        self.assertEqual(page_ids, ["page123"])

    def test_parse_mentions_with_at_symbol_not_part_of_mention(self):
        """Test that @ symbols not followed by mention format are preserved."""
        query = "Email me @ john@example.com about @[Pages](id1)"
        cleaned_query, page_ids = parse_mentions(query)

        # Should only remove the actual mention, preserve other @ symbols
        self.assertEqual(cleaned_query, "Email me @ john@example.com about Pages")
        self.assertEqual(page_ids, ["id1"])

    def test_parse_mentions_with_title_only_single(self):
        """Test parsing a mention with only title (no ID)."""
        query = "Check @[Task List]"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "Check Task List")
        self.assertEqual(page_ids, [])

    def test_parse_mentions_with_title_only_multiple(self):
        """Test parsing multiple mentions with only titles (no IDs)."""
        query = "Compare @[Doc A] with @[Doc B]"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "Compare Doc A with Doc B")
        self.assertEqual(page_ids, [])

    def test_parse_mentions_with_mixed_formats(self):
        """Test parsing mentions with both formats (with and without IDs)."""
        query = "Compare @[Doc A](id1) with @[Doc B]"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "Compare Doc A with Doc B")
        self.assertEqual(page_ids, ["id1"])

    def test_parse_mentions_with_title_only_at_beginning(self):
        """Test parsing title-only mention at the beginning."""
        query = "@[Task List] needs review"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "Task List needs review")
        self.assertEqual(page_ids, [])

    def test_parse_mentions_with_title_only_at_end(self):
        """Test parsing title-only mention at the end."""
        query = "Please review @[Task List]"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "Please review Task List")
        self.assertEqual(page_ids, [])

    def test_parse_mentions_with_title_only_special_characters(self):
        """Test parsing title-only mention with special characters."""
        query = "Check @[Meeting Pages - Q4 2024!]"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "Check Meeting Pages - Q4 2024!")
        self.assertEqual(page_ids, [])

    def test_parse_mentions_with_consecutive_mixed_formats(self):
        """Test parsing consecutive mentions with mixed formats."""
        query = "@[Doc A](id_a)@[Doc B]@[Doc C](id_c)"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "Doc ADoc BDoc C")
        self.assertEqual(page_ids, ["id_a", "id_c"])

    def test_parse_mentions_with_malformed_title_only_no_closing_bracket(self):
        """Test that malformed title-only mentions are not parsed."""
        query = "What is @[Meeting Pages about?"
        cleaned_query, page_ids = parse_mentions(query)

        # Should not match because missing ]
        self.assertEqual(cleaned_query, "What is @[Meeting Pages about?")
        self.assertEqual(page_ids, [])

    def test_parse_mentions_preserves_order_mixed_formats(self):
        """Test that order is preserved with mixed mention formats."""
        query = "@[Third](3) comes after @[First] and @[Second](2)"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "Third comes after First and Second")
        self.assertEqual(page_ids, ["3", "2"])

    def test_parse_mentions_with_title_only_numbers(self):
        """Test parsing title-only mention with numbers in the title."""
        query = "Review @[Meeting 2024-12-06]"
        cleaned_query, page_ids = parse_mentions(query)

        self.assertEqual(cleaned_query, "Review Meeting 2024-12-06")
        self.assertEqual(page_ids, [])

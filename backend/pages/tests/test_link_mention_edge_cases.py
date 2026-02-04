"""
Tests for edge cases in link and mention parsing.

Covers:
- Unicode characters in link text and usernames
- Nested/malformed link syntax
- Circular reference detection and handling
- Special character handling
- Multi-line content with links
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from pages.models import Page, PageLink, PageMention, Project
from pages.models.links import INTERNAL_LINK_PATTERN
from pages.models.mentions import MENTION_PATTERN
from users.models import Org


User = get_user_model()


class LinkParsingUnicodeTests(TestCase):
    """Tests for Unicode handling in link parsing."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        self.org = Org.objects.create(name="Test Org")
        self.org.members.add(self.user)
        self.project = Project.objects.create(
            name="Test Project",
            org=self.org,
            creator=self.user,
        )
        self.source_page = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Source Page",
        )
        self.target_page = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Target Page",
        )

    def test_link_text_with_unicode_characters(self):
        """Links with Unicode characters in link text should be parsed correctly."""
        content = f"Check out [日本語のページ](/pages/{self.target_page.external_id}/)"

        PageLink.objects.sync_links_for_page(self.source_page, content)

        self.assertEqual(PageLink.objects.count(), 1)
        link = PageLink.objects.first()
        self.assertEqual(link.link_text, "日本語のページ")

    def test_link_text_with_emoji(self):
        """Links with emoji in link text should be parsed correctly."""
        content = f"Check out [🚀 Launch Page 🎉](/pages/{self.target_page.external_id}/)"

        PageLink.objects.sync_links_for_page(self.source_page, content)

        self.assertEqual(PageLink.objects.count(), 1)
        link = PageLink.objects.first()
        self.assertEqual(link.link_text, "🚀 Launch Page 🎉")

    def test_link_text_with_cyrillic(self):
        """Links with Cyrillic characters should be parsed correctly."""
        content = f"See [Привет мир](/pages/{self.target_page.external_id}/)"

        PageLink.objects.sync_links_for_page(self.source_page, content)

        self.assertEqual(PageLink.objects.count(), 1)
        link = PageLink.objects.first()
        self.assertEqual(link.link_text, "Привет мир")

    def test_link_text_with_arabic(self):
        """Links with Arabic characters should be parsed correctly."""
        content = f"See [مرحبا بالعالم](/pages/{self.target_page.external_id}/)"

        PageLink.objects.sync_links_for_page(self.source_page, content)

        self.assertEqual(PageLink.objects.count(), 1)
        link = PageLink.objects.first()
        self.assertEqual(link.link_text, "مرحبا بالعالم")

    def test_link_text_with_mixed_scripts(self):
        """Links with mixed Unicode scripts should be parsed correctly."""
        content = f"See [Hello 世界 Привет 🌍](/pages/{self.target_page.external_id}/)"

        PageLink.objects.sync_links_for_page(self.source_page, content)

        self.assertEqual(PageLink.objects.count(), 1)
        link = PageLink.objects.first()
        self.assertEqual(link.link_text, "Hello 世界 Привет 🌍")

    def test_link_text_with_special_unicode_characters(self):
        """Links with special Unicode punctuation should be parsed correctly."""
        link_text = 'Page — with "quotes" and «brackets»'
        content = f"See [{link_text}](/pages/{self.target_page.external_id}/)"

        PageLink.objects.sync_links_for_page(self.source_page, content)

        self.assertEqual(PageLink.objects.count(), 1)
        link = PageLink.objects.first()
        self.assertEqual(link.link_text, link_text)


class MentionParsingUnicodeTests(TestCase):
    """Tests for Unicode handling in mention parsing."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        self.mentioned_user = User.objects.create_user(
            email="mentioned@example.com",
            username="mentioned_user",
            password="testpass123",
        )
        self.org = Org.objects.create(name="Test Org")
        self.org.members.add(self.user)
        self.org.members.add(self.mentioned_user)
        self.project = Project.objects.create(
            name="Test Project",
            org=self.org,
            creator=self.user,
        )
        self.page = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Test Page",
        )

    def test_mention_display_name_with_unicode(self):
        """Mentions with Unicode display names should be parsed correctly."""
        content = f"Hey @[田中太郎](@{self.mentioned_user.external_id}) please check this"

        created, changed = PageMention.objects.sync_mentions_for_page(self.page, content)

        self.assertTrue(changed)
        self.assertEqual(PageMention.objects.count(), 1)
        mention = PageMention.objects.first()
        self.assertEqual(mention.mentioned_user, self.mentioned_user)

    def test_mention_display_name_with_emoji(self):
        """Mentions with emoji in display name should be parsed correctly."""
        content = f"Hey @[🦊 Fox User 🦊](@{self.mentioned_user.external_id}) review this"

        created, changed = PageMention.objects.sync_mentions_for_page(self.page, content)

        self.assertTrue(changed)
        self.assertEqual(PageMention.objects.count(), 1)

    def test_mention_display_name_with_cyrillic(self):
        """Mentions with Cyrillic display names should be parsed correctly."""
        content = f"Привет @[Иван Петров](@{self.mentioned_user.external_id})"

        created, changed = PageMention.objects.sync_mentions_for_page(self.page, content)

        self.assertTrue(changed)
        self.assertEqual(PageMention.objects.count(), 1)


class NestedAndMalformedLinksTests(TestCase):
    """Tests for nested, overlapping, and malformed link syntax."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        self.org = Org.objects.create(name="Test Org")
        self.org.members.add(self.user)
        self.project = Project.objects.create(
            name="Test Project",
            org=self.org,
            creator=self.user,
        )
        self.source_page = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Source",
        )
        self.target_page = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Target",
        )

    def test_link_text_containing_brackets(self):
        """Link text with brackets (but not nested links) should work."""
        # The regex [^\]]+ won't match if there's a ] in the text
        content = f"See [Page [v1]](/pages/{self.target_page.external_id}/)"

        PageLink.objects.sync_links_for_page(self.source_page, content)

        # This will fail to match due to regex limitations - the ] in [v1] breaks parsing
        # This test documents expected (though limited) behavior
        self.assertEqual(PageLink.objects.count(), 0)

    def test_escaped_brackets_in_link_text(self):
        """Link text with escaped brackets should be handled."""
        content = f"See [Page \\[escaped\\]](/pages/{self.target_page.external_id}/)"

        PageLink.objects.sync_links_for_page(self.source_page, content)

        # Escaped brackets are not specially handled
        self.assertEqual(PageLink.objects.count(), 0)

    def test_unclosed_link_syntax(self):
        """Unclosed link syntax should not create links."""
        test_cases = [
            f"[Unclosed link(/pages/{self.target_page.external_id}/)",
            f"[Link text]open parens /pages/{self.target_page.external_id}/)",
            f"[Link text](/pages/{self.target_page.external_id}/",  # Missing closing paren
            f"Link text](/pages/{self.target_page.external_id}/)",  # Missing opening bracket
        ]

        for content in test_cases:
            with self.subTest(content=content):
                PageLink.objects.all().delete()
                PageLink.objects.sync_links_for_page(self.source_page, content)
                self.assertEqual(PageLink.objects.count(), 0, f"Should not match: {content}")

    def test_multiple_links_on_same_line(self):
        """Multiple valid links on the same line should all be parsed."""
        page2 = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Page 2",
        )
        page3 = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Page 3",
        )

        content = f"See [Target](/pages/{self.target_page.external_id}/) and [Page 2](/pages/{page2.external_id}/) and [Page 3](/pages/{page3.external_id}/)"

        PageLink.objects.sync_links_for_page(self.source_page, content)

        self.assertEqual(PageLink.objects.count(), 3)

    def test_link_followed_by_text_with_parens(self):
        """Link followed by parenthetical text should parse correctly."""
        content = f"See [Target](/pages/{self.target_page.external_id}/) (this is extra info)"

        PageLink.objects.sync_links_for_page(self.source_page, content)

        self.assertEqual(PageLink.objects.count(), 1)
        link = PageLink.objects.first()
        self.assertEqual(link.link_text, "Target")

    def test_adjacent_brackets_without_link(self):
        """Adjacent brackets that don't form a link shouldn't match."""
        content = "[not a link][also not a link]"

        PageLink.objects.sync_links_for_page(self.source_page, content)

        self.assertEqual(PageLink.objects.count(), 0)

    def test_empty_link_text(self):
        """Empty link text should not match the regex."""
        content = f"[](/pages/{self.target_page.external_id}/)"

        PageLink.objects.sync_links_for_page(self.source_page, content)

        # [^\]]+ requires at least one character
        self.assertEqual(PageLink.objects.count(), 0)

    def test_whitespace_only_link_text(self):
        """Whitespace-only link text should be parsed (not ideal but expected)."""
        content = f"[   ](/pages/{self.target_page.external_id}/)"

        PageLink.objects.sync_links_for_page(self.source_page, content)

        # The regex will match whitespace-only text
        self.assertEqual(PageLink.objects.count(), 1)
        link = PageLink.objects.first()
        self.assertEqual(link.link_text, "   ")


class NestedAndMalformedMentionsTests(TestCase):
    """Tests for nested and malformed mention syntax."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        self.mentioned_user = User.objects.create_user(
            email="mentioned@example.com",
            username="mentioned",
            password="testpass123",
        )
        self.org = Org.objects.create(name="Test Org")
        self.org.members.add(self.user)
        self.org.members.add(self.mentioned_user)
        self.project = Project.objects.create(
            name="Test Project",
            org=self.org,
            creator=self.user,
        )
        self.page = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Test Page",
        )

    def test_plain_at_symbol_not_matched(self):
        """Plain @ symbols should not create mentions."""
        content = "Contact me at test@example.com for details"

        created, changed = PageMention.objects.sync_mentions_for_page(self.page, content)

        self.assertFalse(changed)
        self.assertEqual(PageMention.objects.count(), 0)

    def test_mention_without_at_prefix_in_id(self):
        """Mention IDs without @ prefix should not match (would be regular links)."""
        # This tests that MENTION_PATTERN requires @ prefix in the ID
        content = f"@[username]({self.mentioned_user.external_id})"  # Missing @ in ID

        created, changed = PageMention.objects.sync_mentions_for_page(self.page, content)

        self.assertFalse(changed)
        self.assertEqual(PageMention.objects.count(), 0)

    def test_multiple_mentions_same_line(self):
        """Multiple mentions on the same line should all be parsed."""
        user2 = User.objects.create_user(
            email="user2@example.com",
            username="user2",
            password="testpass123",
        )
        self.org.members.add(user2)

        content = f"Hey @[mentioned](@{self.mentioned_user.external_id}) and @[user2](@{user2.external_id})!"

        created, changed = PageMention.objects.sync_mentions_for_page(self.page, content)

        self.assertTrue(changed)
        self.assertEqual(PageMention.objects.count(), 2)

    def test_empty_display_name_mention(self):
        """Empty display name in mention should not match."""
        content = f"@[](@{self.mentioned_user.external_id})"

        created, changed = PageMention.objects.sync_mentions_for_page(self.page, content)

        self.assertFalse(changed)
        self.assertEqual(PageMention.objects.count(), 0)


class CircularReferenceTests(TestCase):
    """Tests for circular link reference handling."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        self.org = Org.objects.create(name="Test Org")
        self.org.members.add(self.user)
        self.project = Project.objects.create(
            name="Test Project",
            org=self.org,
            creator=self.user,
        )
        self.page_a = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Page A",
        )
        self.page_b = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Page B",
        )
        self.page_c = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Page C",
        )

    def test_two_page_circular_reference(self):
        """Two pages can link to each other (A → B, B → A)."""
        # A links to B
        content_a = f"See [Page B](/pages/{self.page_b.external_id}/)"
        PageLink.objects.sync_links_for_page(self.page_a, content_a)

        # B links to A
        content_b = f"See [Page A](/pages/{self.page_a.external_id}/)"
        PageLink.objects.sync_links_for_page(self.page_b, content_b)

        # Both links should exist
        self.assertEqual(PageLink.objects.count(), 2)

        # Verify directionality
        self.assertEqual(self.page_a.outgoing_links.count(), 1)
        self.assertEqual(self.page_a.incoming_links.count(), 1)
        self.assertEqual(self.page_b.outgoing_links.count(), 1)
        self.assertEqual(self.page_b.incoming_links.count(), 1)

    def test_three_page_circular_reference(self):
        """Three pages can form a cycle (A → B → C → A)."""
        # A → B
        PageLink.objects.sync_links_for_page(self.page_a, f"See [Page B](/pages/{self.page_b.external_id}/)")
        # B → C
        PageLink.objects.sync_links_for_page(self.page_b, f"See [Page C](/pages/{self.page_c.external_id}/)")
        # C → A
        PageLink.objects.sync_links_for_page(self.page_c, f"See [Page A](/pages/{self.page_a.external_id}/)")

        self.assertEqual(PageLink.objects.count(), 3)

        # Each page has one outgoing and one incoming
        for page in [self.page_a, self.page_b, self.page_c]:
            self.assertEqual(page.outgoing_links.count(), 1)
            self.assertEqual(page.incoming_links.count(), 1)

    def test_self_links_are_ignored(self):
        """Self-referential links (A → A) should be ignored."""
        content = f"See [this page](/pages/{self.page_a.external_id}/)"

        PageLink.objects.sync_links_for_page(self.page_a, content)

        self.assertEqual(PageLink.objects.count(), 0)

    def test_multiple_links_same_target(self):
        """Multiple links to the same target with different text are allowed."""
        content = (
            f"See [Page B](/pages/{self.page_b.external_id}/) and also " f"[Go to B](/pages/{self.page_b.external_id}/)"
        )

        PageLink.objects.sync_links_for_page(self.page_a, content)

        # Both links with different text should be stored
        self.assertEqual(PageLink.objects.count(), 2)
        link_texts = set(PageLink.objects.values_list("link_text", flat=True))
        self.assertEqual(link_texts, {"Page B", "Go to B"})

    def test_duplicate_links_same_text_deduplicated(self):
        """Multiple links to same target with same text are deduplicated."""
        content = (
            f"See [Page B](/pages/{self.page_b.external_id}/) and again " f"[Page B](/pages/{self.page_b.external_id}/)"
        )

        PageLink.objects.sync_links_for_page(self.page_a, content)

        # Only one link should be stored (unique_together constraint)
        self.assertEqual(PageLink.objects.count(), 1)


class MultiLineContentTests(TestCase):
    """Tests for link/mention parsing in multi-line content."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        self.mentioned_user = User.objects.create_user(
            email="mentioned@example.com",
            username="mentioned",
            password="testpass123",
        )
        self.org = Org.objects.create(name="Test Org")
        self.org.members.add(self.user)
        self.org.members.add(self.mentioned_user)
        self.project = Project.objects.create(
            name="Test Project",
            org=self.org,
            creator=self.user,
        )
        self.source_page = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Source",
        )
        self.target_page = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Target",
        )

    def test_links_across_multiple_lines(self):
        """Links on different lines should all be parsed."""
        page2 = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Page 2",
        )
        content = f"""First paragraph with [Target](/pages/{self.target_page.external_id}/).

Second paragraph with [Page 2](/pages/{page2.external_id}/).

Third paragraph with no links."""

        PageLink.objects.sync_links_for_page(self.source_page, content)

        self.assertEqual(PageLink.objects.count(), 2)

    def test_mentions_across_multiple_lines(self):
        """Mentions on different lines should all be parsed."""
        user2 = User.objects.create_user(
            email="user2@example.com",
            username="user2",
            password="testpass123",
        )
        self.org.members.add(user2)

        content = f"""Line 1: @[mentioned](@{self.mentioned_user.external_id})

Line 2: Some text

Line 3: @[user2](@{user2.external_id})"""

        created, changed = PageMention.objects.sync_mentions_for_page(self.source_page, content)

        self.assertTrue(changed)
        self.assertEqual(PageMention.objects.count(), 2)

    def test_link_text_can_span_lines(self):
        """Link text spanning multiple lines is supported by the regex."""
        content = f"""[Multi
line
text](/pages/{self.target_page.external_id}/)"""

        PageLink.objects.sync_links_for_page(self.source_page, content)

        # The regex [^\]]+ matches any character except ], including newlines
        # So multi-line link text is supported
        self.assertEqual(PageLink.objects.count(), 1)
        link = PageLink.objects.first()
        self.assertEqual(link.link_text, "Multi\nline\ntext")


class SpecialCharacterTests(TestCase):
    """Tests for special characters in links and mentions."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        self.mentioned_user = User.objects.create_user(
            email="mentioned@example.com",
            username="mentioned",
            password="testpass123",
        )
        self.org = Org.objects.create(name="Test Org")
        self.org.members.add(self.user)
        self.org.members.add(self.mentioned_user)
        self.project = Project.objects.create(
            name="Test Project",
            org=self.org,
            creator=self.user,
        )
        self.source_page = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Source",
        )
        self.target_page = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Target",
        )

    def test_link_text_with_parentheses(self):
        """Link text containing parentheses should work."""
        content = f"See [Page (version 1)](/pages/{self.target_page.external_id}/)"

        PageLink.objects.sync_links_for_page(self.source_page, content)

        self.assertEqual(PageLink.objects.count(), 1)
        link = PageLink.objects.first()
        self.assertEqual(link.link_text, "Page (version 1)")

    def test_link_text_with_quotes(self):
        """Link text with various quote characters should work."""
        content = f"""See [Page "quoted" and 'single'](/pages/{self.target_page.external_id}/)"""

        PageLink.objects.sync_links_for_page(self.source_page, content)

        self.assertEqual(PageLink.objects.count(), 1)
        link = PageLink.objects.first()
        self.assertEqual(link.link_text, "Page \"quoted\" and 'single'")

    def test_link_text_with_html_entities(self):
        """Link text with HTML-like content should work (stored as-is)."""
        content = f"See [<script>alert</script>](/pages/{self.target_page.external_id}/)"

        PageLink.objects.sync_links_for_page(self.source_page, content)

        self.assertEqual(PageLink.objects.count(), 1)
        link = PageLink.objects.first()
        self.assertEqual(link.link_text, "<script>alert</script>")

    def test_link_text_with_markdown_formatting(self):
        """Link text with markdown formatting characters should work."""
        content = f"See [**Bold** and _italic_](/pages/{self.target_page.external_id}/)"

        PageLink.objects.sync_links_for_page(self.source_page, content)

        self.assertEqual(PageLink.objects.count(), 1)
        link = PageLink.objects.first()
        self.assertEqual(link.link_text, "**Bold** and _italic_")

    def test_mention_display_with_special_characters(self):
        """Mention display names with special characters should work."""
        content = f"Hey @[User (Admin) & Co.](@{self.mentioned_user.external_id})"

        created, changed = PageMention.objects.sync_mentions_for_page(self.source_page, content)

        self.assertTrue(changed)
        self.assertEqual(PageMention.objects.count(), 1)

    def test_link_with_trailing_slash_optional(self):
        """Links should work with or without trailing slash."""
        # With trailing slash
        content1 = f"See [Target](/pages/{self.target_page.external_id}/)"
        PageLink.objects.sync_links_for_page(self.source_page, content1)
        self.assertEqual(PageLink.objects.count(), 1)

        # Without trailing slash
        PageLink.objects.all().delete()
        content2 = f"See [Target](/pages/{self.target_page.external_id})"
        PageLink.objects.sync_links_for_page(self.source_page, content2)
        self.assertEqual(PageLink.objects.count(), 1)


class RegexPatternDirectTests(TestCase):
    """Direct tests of the regex patterns to verify edge case handling."""

    def test_internal_link_pattern_matches_valid_links(self):
        """INTERNAL_LINK_PATTERN should match standard internal links."""
        valid_cases = [
            ("[Page](/pages/abc123/)", "Page", "abc123"),
            ("[Page](/pages/abc123)", "Page", "abc123"),  # No trailing slash
            ("[My Page Title](/pages/XYZ789/)", "My Page Title", "XYZ789"),
            ("[A](/pages/a/)", "A", "a"),  # Single char
            ("[日本語](/pages/abc123/)", "日本語", "abc123"),  # Unicode text
        ]

        for content, expected_text, expected_id in valid_cases:
            with self.subTest(content=content):
                match = INTERNAL_LINK_PATTERN.search(content)
                self.assertIsNotNone(match, f"Should match: {content}")
                self.assertEqual(match.group(1), expected_text)
                self.assertEqual(match.group(2), expected_id)

    def test_internal_link_pattern_rejects_invalid(self):
        """INTERNAL_LINK_PATTERN should not match invalid formats."""
        invalid_cases = [
            "[](/pages/abc123/)",  # Empty text
            "[Page](/pages//)",  # Empty ID
            "[Page](/pages/abc-123/)",  # Hyphen in ID (not alphanumeric)
            "[Page](/pages/abc_123/)",  # Underscore in ID (not alphanumeric)
            "[Page](https://example.com/)",  # External URL
            "[Page](/other/abc123/)",  # Wrong path
            "Page(/pages/abc123/)",  # Missing brackets
        ]

        for content in invalid_cases:
            with self.subTest(content=content):
                match = INTERNAL_LINK_PATTERN.search(content)
                self.assertIsNone(match, f"Should not match: {content}")

    def test_mention_pattern_matches_valid_mentions(self):
        """MENTION_PATTERN should match standard mentions."""
        valid_cases = [
            ("@[user](@abc123)", "user", "abc123"),
            ("@[John Doe](@XYZ789)", "John Doe", "XYZ789"),
            ("@[日本語](@abc123)", "日本語", "abc123"),  # Unicode display name
        ]

        for content, expected_name, expected_id in valid_cases:
            with self.subTest(content=content):
                match = MENTION_PATTERN.search(content)
                self.assertIsNotNone(match, f"Should match: {content}")
                self.assertEqual(match.group(1), expected_name)
                self.assertEqual(match.group(2), expected_id)

    def test_mention_pattern_rejects_invalid(self):
        """MENTION_PATTERN should not match invalid formats."""
        invalid_cases = [
            "@[](@abc123)",  # Empty display name
            "@[user](abc123)",  # Missing @ in ID
            "@[user](@)",  # Empty ID
            "[user](@abc123)",  # Missing @ at start
            "@user(@abc123)",  # Missing brackets around name
            "@[user](@abc-123)",  # Hyphen in ID
        ]

        for content in invalid_cases:
            with self.subTest(content=content):
                match = MENTION_PATTERN.search(content)
                self.assertIsNone(match, f"Should not match: {content}")


class LinkAndMentionMixedContentTests(TestCase):
    """Tests for content containing both links and mentions."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        self.mentioned_user = User.objects.create_user(
            email="mentioned@example.com",
            username="mentioned",
            password="testpass123",
        )
        self.org = Org.objects.create(name="Test Org")
        self.org.members.add(self.user)
        self.org.members.add(self.mentioned_user)
        self.project = Project.objects.create(
            name="Test Project",
            org=self.org,
            creator=self.user,
        )
        self.source_page = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Source",
        )
        self.target_page = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Target",
        )

    def test_content_with_both_links_and_mentions(self):
        """Content with both links and mentions should parse both correctly."""
        content = f"Hey @[mentioned](@{self.mentioned_user.external_id}), check out [Target](/pages/{self.target_page.external_id}/)!"

        # Sync links
        PageLink.objects.sync_links_for_page(self.source_page, content)
        self.assertEqual(PageLink.objects.count(), 1)

        # Sync mentions
        created, changed = PageMention.objects.sync_mentions_for_page(self.source_page, content)
        self.assertTrue(changed)
        self.assertEqual(PageMention.objects.count(), 1)

    def test_mention_format_not_confused_with_link(self):
        """Mention format (@[name](@id)) should not be parsed as a link."""
        content = f"@[mentioned](@{self.mentioned_user.external_id})"

        PageLink.objects.sync_links_for_page(self.source_page, content)

        # The mention format uses @id which doesn't start with /pages/
        self.assertEqual(PageLink.objects.count(), 0)

    def test_link_format_not_confused_with_mention(self):
        """Link format ([text](/pages/id/)) should not be parsed as a mention."""
        content = f"[Target](/pages/{self.target_page.external_id}/)"

        created, changed = PageMention.objects.sync_mentions_for_page(self.source_page, content)

        # Links don't start with @ and ID doesn't have @ prefix
        self.assertFalse(changed)
        self.assertEqual(PageMention.objects.count(), 0)

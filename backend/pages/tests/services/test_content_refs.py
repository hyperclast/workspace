"""Tests for pages.services.content_refs.parse_page_refs.

The collaboration snapshot sync path in `collab.tasks.sync_snapshot_with_page`
uses `parse_page_refs` to extract page links, @mentions, and file links in a
single regex walk over the content. The per-manager `sync_*_for_page`
methods (used by other callers such as `imports/services/notion.py`) keep
their original regexes. These tests lock in parity between the two
implementations so future regex edits to one side cannot silently drift from
the other.
"""

import uuid

from django.test import SimpleTestCase

from core.helpers import is_valid_uuid
from filehub.models.links import FILE_LINK_PATTERN
from pages.models.links import INTERNAL_LINK_PATTERN
from pages.models.mentions import MENTION_PATTERN
from pages.services.content_refs import parse_page_refs


def _file_link_tuples(content):
    """Reproduce the per-manager FileLinkManager parse of `content`."""
    result = []
    for match in FILE_LINK_PATTERN.finditer(content):
        link_text = match.group(1)
        target_file_id = match.group(3)
        if is_valid_uuid(target_file_id):
            result.append((link_text, target_file_id))
    return result


def _page_link_tuples(content):
    """Reproduce the per-manager PageLinkManager parse of `content`."""
    return [(m.group(1), m.group(2)) for m in INTERNAL_LINK_PATTERN.finditer(content)]


def _mention_ids(content):
    """Reproduce the per-manager PageMentionManager parse of `content`."""
    return [m.group(2) for m in MENTION_PATTERN.finditer(content)]


class ParsePageRefsEmptyTests(SimpleTestCase):
    def test_empty_string(self):
        mentions, page_links, file_links = parse_page_refs("")
        self.assertEqual(mentions, [])
        self.assertEqual(page_links, [])
        self.assertEqual(file_links, [])

    def test_no_markdown_links(self):
        mentions, page_links, file_links = parse_page_refs("Just some plain prose, no refs here.")
        self.assertEqual(mentions, [])
        self.assertEqual(page_links, [])
        self.assertEqual(file_links, [])


class ParsePageRefsPageLinkTests(SimpleTestCase):
    def test_single_page_link_trailing_slash(self):
        content = "See [Target](/pages/abc123xyz0/)"
        _, page_links, _ = parse_page_refs(content)
        self.assertEqual(page_links, [("Target", "abc123xyz0")])

    def test_single_page_link_no_trailing_slash(self):
        content = "See [Target](/pages/abc123xyz0)"
        _, page_links, _ = parse_page_refs(content)
        self.assertEqual(page_links, [("Target", "abc123xyz0")])

    def test_multiple_page_links(self):
        content = "[A](/pages/aaaaaaaaaa/) and [B](/pages/bbbbbbbbbb/)"
        _, page_links, _ = parse_page_refs(content)
        self.assertEqual(page_links, [("A", "aaaaaaaaaa"), ("B", "bbbbbbbbbb")])

    def test_page_link_with_query_string_is_rejected(self):
        # Only bare /pages/{id}/ URLs are internal page links.
        content = "[x](/pages/abc?foo=bar)"
        _, page_links, _ = parse_page_refs(content)
        self.assertEqual(page_links, [])


class ParsePageRefsMentionTests(SimpleTestCase):
    def test_single_mention(self):
        content = "Hi @[alice](@user0user0)!"
        mentions, page_links, _ = parse_page_refs(content)
        self.assertEqual(mentions, ["user0user0"])
        self.assertEqual(page_links, [])

    def test_multiple_mentions_preserves_order_and_duplicates(self):
        # parse_page_refs does not deduplicate — deduplication is the caller's
        # responsibility (sync_parsed_mentions does it via set()).
        content = "@[a](@user0000aa) @[b](@user0000bb) @[a](@user0000aa)"
        mentions, _, _ = parse_page_refs(content)
        self.assertEqual(mentions, ["user0000aa", "user0000bb", "user0000aa"])

    def test_mention_syntax_without_at_prefix_is_not_a_mention(self):
        content = "[fake](@user0000aa)"
        mentions, page_links, file_links = parse_page_refs(content)
        self.assertEqual(mentions, [])
        self.assertEqual(page_links, [])
        self.assertEqual(file_links, [])


class ParsePageRefsFileLinkTests(SimpleTestCase):
    def test_relative_file_link(self):
        file_id = str(uuid.uuid4())
        content = f"[img](/files/proj1234/{file_id}/tok_abc/)"
        _, _, file_links = parse_page_refs(content)
        self.assertEqual(file_links, [("img", file_id)])

    def test_absolute_file_link(self):
        file_id = str(uuid.uuid4())
        content = f"[img](https://files.example.test/files/proj1234/{file_id}/tok_abc/)"
        _, _, file_links = parse_page_refs(content)
        self.assertEqual(file_links, [("img", file_id)])

    def test_file_link_without_trailing_slash(self):
        file_id = str(uuid.uuid4())
        content = f"[img](/files/proj1234/{file_id}/tok_abc)"
        _, _, file_links = parse_page_refs(content)
        self.assertEqual(file_links, [("img", file_id)])

    def test_file_link_with_non_uuid_is_dropped(self):
        content = "[img](/files/proj1234/not-a-real-uuid/tok/)"
        _, _, file_links = parse_page_refs(content)
        self.assertEqual(file_links, [])


class ParsePageRefsFallthroughTests(SimpleTestCase):
    """`@` before `[..](..)` where the URL is not a mention URL.

    Old per-manager behavior: MENTION_PATTERN requires URL = `@user_id`, so it
    skips; INTERNAL_LINK_PATTERN / FILE_LINK_PATTERN are unanchored and still
    match the `[..](..)` portion.

    New parser must fall through the `@?` branch so page/file URLs still match.
    """

    def test_at_prefix_before_page_link_is_classified_as_page_link(self):
        content = "@[label](/pages/abc123xyz0/)"
        mentions, page_links, file_links = parse_page_refs(content)
        self.assertEqual(mentions, [])
        self.assertEqual(page_links, [("label", "abc123xyz0")])
        self.assertEqual(file_links, [])

    def test_at_prefix_before_file_link_is_classified_as_file_link(self):
        file_id = str(uuid.uuid4())
        content = f"@[img](/files/proj1234/{file_id}/tok/)"
        mentions, page_links, file_links = parse_page_refs(content)
        self.assertEqual(mentions, [])
        self.assertEqual(page_links, [])
        self.assertEqual(file_links, [("img", file_id)])

    def test_at_prefix_with_non_url_target_is_dropped(self):
        content = "@[label](not-a-url)"
        mentions, page_links, file_links = parse_page_refs(content)
        self.assertEqual(mentions, [])
        self.assertEqual(page_links, [])
        self.assertEqual(file_links, [])


class ParsePageRefsMixedContentTests(SimpleTestCase):
    def test_mixed_references_in_single_string(self):
        file_id = str(uuid.uuid4())
        content = (
            "Intro paragraph.\n"
            "Ping @[alice](@user0user0) about the doc.\n"
            "See also [Plan](/pages/aaaaaaaaaa/) and\n"
            f"the attachment [spec.pdf](/files/proj1234/{file_id}/tok_abc/).\n"
            "Unrelated link [docs](https://example.com/docs) should be ignored."
        )
        mentions, page_links, file_links = parse_page_refs(content)

        self.assertEqual(mentions, ["user0user0"])
        self.assertEqual(page_links, [("Plan", "aaaaaaaaaa")])
        self.assertEqual(file_links, [("spec.pdf", file_id)])


class ParsePageRefsParityTests(SimpleTestCase):
    """For representative corpora, assert the new combined parser returns the
    same refs as the old per-manager regexes would.
    """

    CORPORA = [
        "",
        "No refs here at all.",
        "Plain [link](https://example.com/) only.",
        "[A](/pages/aaaaaaaaaa/) and [B](/pages/bbbbbbbbbb)",
        "@[alice](@user0user0) and @[bob](@user000bob0)",
        "@[dup](@userdup0000) @[dup](@userdup0000)",
        "[img](/files/proj/{uuid}/tok/)",
        "[img](https://h.example/files/proj/{uuid}/tok/)",
        "[bad](/files/proj/not-uuid/tok/)",
        "@[label](/pages/aaaaaaaaaa/)",
        "@[img](/files/proj/{uuid}/tok/)",
        "@[label](not-a-url)",
        (
            "Mix: @[a](@user000000a) then [P](/pages/aaaaaaaaaa/) "
            "then [F](/files/proj/{uuid}/tok/) and @[b](@user000000b)"
        ),
    ]

    def _expand(self, s):
        return s.format(uuid=str(uuid.uuid4()))

    def test_parity_with_per_manager_regexes(self):
        for template in self.CORPORA:
            with self.subTest(template=template):
                content = self._expand(template)
                mentions, page_links, file_links = parse_page_refs(content)

                self.assertEqual(mentions, _mention_ids(content))
                # Page-link parity: in the old path, INTERNAL_LINK_PATTERN
                # never matches a URL that starts with `@`, but the new parser
                # falls through from the `@?` branch and can classify
                # `@[label](/pages/xxx/)` as a page link. That's the intended
                # and tested behavior. Since INTERNAL_LINK_PATTERN is
                # unanchored, it also matches the `[label](/pages/xxx/)`
                # substring — so both paths converge on the same ref.
                self.assertEqual(page_links, _page_link_tuples(content))
                self.assertEqual(file_links, _file_link_tuples(content))

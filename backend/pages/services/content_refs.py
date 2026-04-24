"""
Combined parser for page content references (mentions, internal page links,
internal file links).

The existing per-manager sync_*_for_page methods each run their own regex sweep
over the full content. In the collaboration snapshot path
(`collab.tasks.sync_snapshot_with_page`), all three run back-to-back against
the same content, tripling the parse cost on large documents.

This module exposes a single-pass parser that classifies each `[text](url)`
match by URL shape, plus lightweight `sync_parsed_*` entry points on each
manager that accept the already-parsed tuples. Callers that only need one
kind of reference should keep using the existing per-manager sync methods.
"""

import re

from core.helpers import is_valid_uuid

# One regex for all markdown-style link references, including the optional
# leading '@' used by @mentions. URL classification happens in Python below.
_LINK_PATTERN = re.compile(r"(@?)\[([^\]]+)\]\(([^)]+)\)")

# Shapes the URL portion may take. Match these on just the captured URL so we
# don't re-scan the whole content.
_MENTION_URL = re.compile(r"^@([a-zA-Z0-9]+)$")
_PAGE_URL = re.compile(r"^/pages/([a-zA-Z0-9]+)/?$")
_FILE_URL = re.compile(r"^(?:https?://[^/]+)?/files/[a-zA-Z0-9]+/([a-zA-Z0-9-]+)/[a-zA-Z0-9_-]+/?$")


def parse_page_refs(content):
    """Return (mentions, page_links, file_links) from a single content walk.

    - mentions: list of user_external_id (str) — link text is unused downstream
    - page_links: list of (link_text, target_page_external_id)
    - file_links: list of (link_text, target_file_external_id)   (UUID-validated)
    """
    mentions = []
    page_links = []
    file_links = []

    for m in _LINK_PATTERN.finditer(content):
        at_prefix, link_text, url = m.group(1), m.group(2), m.group(3)

        if at_prefix:
            mention_match = _MENTION_URL.match(url)
            if mention_match:
                mentions.append(mention_match.group(1))
                continue
            # The leading '@' wasn't part of a mention (URL doesn't look like
            # @user_id) — treat it as an incidental literal before a normal
            # markdown link and fall through so a page/file URL can still match.

        page_match = _PAGE_URL.match(url)
        if page_match:
            page_links.append((link_text, page_match.group(1)))
            continue

        file_match = _FILE_URL.match(url)
        if file_match:
            file_id = file_match.group(1)
            if is_valid_uuid(file_id):
                file_links.append((link_text, file_id))

    return mentions, page_links, file_links

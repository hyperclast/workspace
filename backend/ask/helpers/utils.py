import re
from typing import List, Tuple


def parse_mentions(query: str) -> Tuple[str, List[str]]:
    """
    Parse @mentions from a query string.

    Extracts mentions in two formats:
    1. @[page title](page_id) - with both title and ID
    2. @[page title] - with only title (no ID)

    Returns the cleaned query (with IDs removed but titles preserved) along with
    a list of mentioned page IDs.

    The page titles are kept in the query to preserve semantic context for
    the LLM, while the IDs are extracted for page retrieval.

    Malformed mentions (e.g., @[title]abc123) where the pattern looks incomplete)
    are not parsed and left as-is to avoid false positives.

    Args:
        query: The query string potentially containing @mentions.

    Returns:
        A tuple of (cleaned_query, list_of_page_ids) where:
        - cleaned_query: Query with @[title](id) and @[title] replaced by "title"
        - list_of_page_ids: List of page external IDs that were mentioned

    Examples:
        >>> parse_mentions("What is @[Meeting Pages](abc123) about?")
        ("What is Meeting Pages about?", ["abc123"])

        >>> parse_mentions("Summarize @[Page 1](id1) and @[Page 2](id2)")
        ("Summarize Page 1 and Page 2", ["id1", "id2"])

        >>> parse_mentions("Check @[Task List]")
        ("Check Task List", [])

        >>> parse_mentions("What is @[Meeting Pages]abc123) about?")
        ("What is @[Meeting Pages]abc123) about?", [])

        >>> parse_mentions("No mentions here")
        ("No mentions here", [])
    """
    # Pattern matches: @[any text except ]](any text except ))
    # Format: @[page title](page_id)
    mention_with_id_pattern = r"@\[([^\]]+)\]\(([^)]+)\)"

    # Find all matches with IDs
    matches = re.findall(mention_with_id_pattern, query)

    # Extract page IDs (second group in each match)
    page_ids = [page_id for title, page_id in matches]

    # Replace @[title](id) with just "title" to preserve semantic context
    cleaned_query = re.sub(mention_with_id_pattern, r"\1", query)

    # Pattern matches: @[any text except ]] (without the (id) part)
    # Format: @[page title]
    # Only match when NOT followed by characters that look like a malformed (id)
    # Specifically, don't match if followed by: alphanumeric+) or just )
    # This prevents matching malformed mentions like @[title]abc123)
    # But allows @[title] at end of string, before whitespace, or before punctuation
    mention_without_id_pattern = r"@\[([^\]]+)\](?![a-zA-Z0-9]*\))"

    # Replace @[title] with just "title"
    cleaned_query = re.sub(mention_without_id_pattern, r"\1", cleaned_query)

    return cleaned_query, page_ids

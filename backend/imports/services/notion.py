"""
Notion export parser service.

This module handles parsing Notion export zip files and transforming
the content into a format suitable for Hyperclast pages.
"""

import logging
import os
import re
import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO
from urllib.parse import unquote

from django.conf import settings

from imports.constants import (
    NOTION_HASH_MAX_LENGTH,
    NOTION_HASH_MIN_LENGTH,
    NOTION_NESTED_ZIP_PATTERN,
)
from imports.exceptions import (
    ImportExtractedSizeExceededError,
    ImportExtractionTimeoutError,
    ImportInvalidZipError,
    ImportNestedArchiveError,
    ImportParseError,
)

logger = logging.getLogger(__name__)


@dataclass
class ParsedPage:
    """Represents a parsed page from an import source."""

    title: str
    content: str
    original_path: str
    source_hash: str  # Notion: hash from filename, Obsidian: relative filepath
    filetype: str = "md"  # File type: "md" for markdown, "csv" for databases
    children: list["ParsedPage"] = field(default_factory=list)


def _is_safe_path(base_dir: Path, target_path: Path) -> bool:
    """
    Ensure target_path is within base_dir to prevent path traversal.

    Args:
        base_dir: The base directory that should contain the target.
        target_path: The path to validate.

    Returns:
        True if target_path is within base_dir, False otherwise.
    """
    try:
        target_path.resolve().relative_to(base_dir.resolve())
        return True
    except ValueError:
        return False


def extract_zip_safely(
    zip_path: Path,
    dest_dir: Path,
    max_extracted_size: int | None = None,
    timeout_seconds: int | None = None,
) -> dict:
    """
    Extract zip file with streaming validation and fail-fast behavior.

    This function extracts files one at a time while tracking total extracted size
    and elapsed time, failing immediately if thresholds are exceeded.

    Args:
        zip_path: Path to the zip file to extract.
        dest_dir: Directory to extract files into.
        max_extracted_size: Maximum total bytes to extract. Defaults to settings value.
        timeout_seconds: Maximum seconds for extraction. Defaults to settings value.

    Returns:
        dict with extraction statistics:
            - files_extracted: Number of files extracted
            - bytes_extracted: Total bytes extracted
            - duration_seconds: Time taken for extraction

    Raises:
        ImportInvalidZipError: If zip is invalid or contains unsafe paths.
        ImportExtractedSizeExceededError: If extraction would exceed size limit.
        ImportExtractionTimeoutError: If extraction exceeds timeout.
    """
    max_extracted_size = max_extracted_size or getattr(
        settings, "WS_IMPORTS_MAX_UNCOMPRESSED_SIZE_BYTES", 5 * 1024**3
    )
    timeout_seconds = timeout_seconds or getattr(settings, "WS_IMPORTS_EXTRACTION_TIMEOUT_SECONDS", 300)

    start_time = time.time()
    total_extracted = 0
    files_extracted = 0

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                # Timeout check
                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    raise ImportExtractionTimeoutError(
                        f"Extraction exceeded {timeout_seconds}s timeout",
                        details={
                            "elapsed_seconds": elapsed,
                            "files_extracted": files_extracted,
                            "bytes_extracted": total_extracted,
                        },
                    )

                # Skip directories (they have no content to extract)
                if info.is_dir():
                    continue

                # Size check before extraction (using declared size from zip metadata)
                if total_extracted + info.file_size > max_extracted_size:
                    raise ImportExtractedSizeExceededError(
                        f"Extraction would exceed {max_extracted_size} bytes limit",
                        details={
                            "current_extracted": total_extracted,
                            "next_file_size": info.file_size,
                            "limit": max_extracted_size,
                        },
                    )

                # Safe path construction
                target_path = dest_dir / info.filename
                if not _is_safe_path(dest_dir, target_path):
                    raise ImportInvalidZipError(f"Unsafe path in zip: {info.filename}")

                # Create parent directories
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # Extract single file with chunked reading for memory efficiency
                chunk_size = 64 * 1024  # 64KB chunks
                with zf.open(info) as source, open(target_path, "wb") as target:
                    while True:
                        chunk = source.read(chunk_size)
                        if not chunk:
                            break
                        target.write(chunk)
                        total_extracted += len(chunk)

                files_extracted += 1

    except zipfile.BadZipFile as e:
        raise ImportInvalidZipError(f"Invalid zip file: {e}") from e

    duration = time.time() - start_time
    logger.debug(f"Extracted {files_extracted} files ({total_extracted} bytes) in {duration:.2f}s from {zip_path.name}")

    return {
        "files_extracted": files_extracted,
        "bytes_extracted": total_extracted,
        "duration_seconds": duration,
    }


def parse_notion_filename(filename: str) -> tuple[str, str]:
    """
    Extract title and hash from a Notion export filename.

    Notion filenames follow the pattern: "{Title} {hash}.md"
    The hash is typically 32 hex characters at the end before the extension.

    Args:
        filename: The filename to parse (e.g., "My Notes abc123def456.md")

    Returns:
        Tuple of (title, hash). If no hash found, returns (title, "").

    Examples:
        >>> parse_notion_filename("My Notes abc123def456789012345678901234.md")
        ('My Notes', 'abc123def456789012345678901234')
        >>> parse_notion_filename("Simple Page.md")
        ('Simple Page', '')
        >>> parse_notion_filename("Meeting 2024-01-15 deadbeef12345678.md")
        ('Meeting 2024-01-15', 'deadbeef12345678')
    """
    # Remove extension
    name = filename
    if name.endswith(".md"):
        name = name[:-3]
    elif name.endswith(".csv"):
        name = name[:-4]

    # Pattern: space followed by hex characters at the end
    pattern = rf"\s+([a-f0-9]{{{NOTION_HASH_MIN_LENGTH},{NOTION_HASH_MAX_LENGTH}}})$"
    match = re.search(pattern, name, re.IGNORECASE)

    if match:
        source_hash = match.group(1)
        title = name[: match.start()].strip()
        return title, source_hash

    # No hash found - return full name as title
    return name.strip(), ""


def extract_zip(file_obj: BinaryIO, extract_to: Path | None = None) -> Path:
    """
    Extract a Notion export zip file to a temporary directory.

    Handles nested zip files (e.g., ExportBlock-*-Part-*.zip) that Notion
    creates for block-level exports or large workspaces.

    Uses streaming extraction with fail-fast behavior for safety.

    Args:
        file_obj: File-like object containing the zip data
        extract_to: Optional path to extract to. If None, creates a temp directory.

    Returns:
        Path to the extracted directory.

    Raises:
        ImportInvalidZipError: If the file is not a valid zip archive or has unsafe paths.
        ImportExtractedSizeExceededError: If extraction exceeds size limit.
        ImportExtractionTimeoutError: If extraction exceeds timeout.
    """
    if extract_to is None:
        extract_to = Path(tempfile.mkdtemp(prefix="notion_import_"))

    # Write file_obj to a temporary file so we can use extract_zip_safely
    # (which requires a Path, not a file object)
    temp_zip_path = extract_to / "_temp_upload.zip"

    try:
        # Write the file object to disk
        with open(temp_zip_path, "wb") as temp_file:
            shutil.copyfileobj(file_obj, temp_file)

        # Use streaming extraction with safety checks
        extract_zip_safely(temp_zip_path, extract_to)

    except (ImportInvalidZipError, ImportExtractedSizeExceededError, ImportExtractionTimeoutError):
        # Clean up temp directory on error
        if extract_to.exists():
            shutil.rmtree(extract_to)
        raise

    finally:
        # Always remove the temp zip file
        if temp_zip_path.exists():
            temp_zip_path.unlink()

    # Handle nested zip files (Notion block exports contain inner zips)
    _extract_nested_zips(extract_to)

    return extract_to


def _extract_nested_zips(
    directory: Path,
    current_depth: int = 1,
    max_depth: int | None = None,
) -> None:
    """
    Extract Notion's nested ExportBlock-*.zip files with depth limiting.

    Notion exports (especially block-level exports) wrap content in nested zips
    like ExportBlock-*-Part-*.zip. This function extracts them in place while
    enforcing a maximum nesting depth for security.

    Only processes zips matching the Notion pattern (ExportBlock-*) to prevent
    arbitrary nested archive attacks.

    Args:
        directory: Path to the extracted directory to check for nested zips.
        current_depth: Current nesting level (starts at 1).
        max_depth: Maximum allowed nesting depth. Defaults to settings value.

    Raises:
        ImportNestedArchiveError: If nesting depth exceeds the limit.
    """
    max_depth = max_depth or getattr(settings, "WS_IMPORTS_MAX_NESTED_ZIP_DEPTH", 2)

    # Check depth limit before processing
    if current_depth > max_depth:
        raise ImportNestedArchiveError(
            f"Nested zip depth {current_depth} exceeds maximum {max_depth}",
            details={"current_depth": current_depth, "max_depth": max_depth},
        )

    # Find all zip files at the top level
    zip_files = [f for f in directory.iterdir() if f.is_file() and f.suffix == ".zip"]

    if not zip_files:
        return

    # Check if the directory contains ONLY zip files (typical Notion nested export)
    all_files = [f for f in directory.iterdir() if f.is_file()]
    only_zips = len(zip_files) == len(all_files)

    if not only_zips:
        # Mixed content - don't extract nested zips to avoid confusion
        return

    # Only process Notion-pattern nested zips (ExportBlock-*-Part-*.zip)
    notion_zips = [f for f in zip_files if NOTION_NESTED_ZIP_PATTERN in f.name]
    non_notion_zips = [f for f in zip_files if NOTION_NESTED_ZIP_PATTERN not in f.name]

    # Reject non-Notion nested archives
    if non_notion_zips:
        raise ImportNestedArchiveError(
            f"Archive contains forbidden nested archives: {[f.name for f in non_notion_zips[:5]]}",
            details={"forbidden_archives": [f.name for f in non_notion_zips]},
        )

    # Extract each Notion nested zip using streaming extraction
    for zip_path in notion_zips:
        try:
            # Use streaming extraction with safety checks
            extract_zip_safely(zip_path, directory)

            # Remove the nested zip after extraction
            zip_path.unlink()

            logger.debug(f"Extracted nested zip: {zip_path.name} (depth {current_depth})")

        except zipfile.BadZipFile:
            # Skip invalid nested zips but log a warning
            logger.warning(f"Skipping invalid nested zip: {zip_path.name}")
            continue

    # Recursively handle any further nested zips (with incremented depth)
    # Look for new directories that might contain nested zips
    for item in directory.iterdir():
        if item.is_dir():
            _extract_nested_zips(item, current_depth + 1, max_depth)


def _find_child_directory(parent_dir: Path, stem: str, title: str) -> Path | None:
    """
    Find the child directory for a Notion page.

    Notion exports use title-only folder names (without the hash suffix).
    For example:
        - File: "Test Pages 2e3fd10b505a80219203dfbe1efb387f.md"
        - Folder: "Test Pages/" (NOT "Test Pages 2e3fd10b505a80219203dfbe1efb387f/")

    This function tries multiple patterns to find the matching folder:
    1. Title only (what Notion actually exports): "Test Pages/"
    2. Full stem with hash (for backwards compatibility): "Test Pages 2e3fd10b.../""

    Args:
        parent_dir: Directory containing the .md file
        stem: Full filename without extension (title + hash)
        title: Extracted title (without hash)

    Returns:
        Path to the child directory if found, None otherwise.
    """
    # Try title-only first (what Notion actually exports)
    title_dir = parent_dir / title
    if title_dir.is_dir():
        return title_dir

    # Fall back to full stem with hash (for backwards compatibility or edge cases)
    stem_dir = parent_dir / stem
    if stem_dir.is_dir():
        return stem_dir

    return None


def build_page_tree(extracted_path: Path) -> list[ParsedPage]:
    """
    Build a tree of parsed pages from an extracted Notion export.

    Walks the directory structure and parses all markdown files.
    Maintains parent-child relationships based on folder structure.

    Args:
        extracted_path: Path to the extracted Notion export directory.

    Returns:
        List of top-level ParsedPage objects (with nested children).
    """
    pages = []

    def process_directory(dir_path: Path, relative_base: str = "") -> list[ParsedPage]:
        """Recursively process a directory and its subdirectories."""
        result = []

        # Get all items in directory, sorted for consistent ordering
        try:
            items = sorted(dir_path.iterdir())
        except OSError:
            return result

        for item in items:
            if item.is_file() and item.suffix == ".md":
                # Parse markdown file
                original_path = os.path.join(relative_base, item.name) if relative_base else item.name
                parsed = parse_markdown_file(item, original_path)
                if parsed:
                    # Check for corresponding subdirectory with children
                    # Notion exports use title-only folder names (without the hash)
                    # e.g., "Test Pages 2e3fd10b505a80219203dfbe1efb387f.md" -> "Test Pages/"
                    child_dir = _find_child_directory(dir_path, item.stem, parsed.title)
                    if child_dir and child_dir.is_dir():
                        child_dir_name = child_dir.name
                        child_relative = (
                            os.path.join(relative_base, child_dir_name) if relative_base else child_dir_name
                        )
                        parsed.children = process_directory(child_dir, child_relative)
                    result.append(parsed)

            elif item.is_file() and item.suffix == ".csv":
                # Handle CSV files (database exports)
                # Skip _all.csv files - Notion exports both {name}.csv and {name}_all.csv
                # The _all variant includes hidden columns, which is redundant
                if item.stem.endswith("_all"):
                    continue
                original_path = os.path.join(relative_base, item.name) if relative_base else item.name
                parsed = _parse_csv_file(item, original_path)
                if parsed:
                    # Check for corresponding subdirectory with database row pages
                    # Same logic as .md files — Notion databases export row pages
                    # as .md files inside a companion directory
                    child_dir = _find_child_directory(dir_path, item.stem, parsed.title)
                    if child_dir and child_dir.is_dir():
                        child_dir_name = child_dir.name
                        child_relative = (
                            os.path.join(relative_base, child_dir_name) if relative_base else child_dir_name
                        )
                        parsed.children = process_directory(child_dir, child_relative)
                    result.append(parsed)

        return result

    pages = process_directory(extracted_path)
    return pages


def parse_markdown_file(filepath: Path, original_path: str) -> ParsedPage | None:
    """
    Parse a single Notion markdown file.

    Args:
        filepath: Path to the markdown file.
        original_path: Original path relative to export root (for tracking).

    Returns:
        ParsedPage object or None if file couldn't be parsed.
    """
    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        # Log error but don't fail the entire import
        return None

    # Extract title and hash from filename
    title, source_hash = parse_notion_filename(filepath.name)

    # Transform content
    transformed_content = transform_content(content)

    # If content starts with a heading that matches the title, remove it
    # (Notion often duplicates the title as the first heading)
    transformed_content = _remove_duplicate_title(transformed_content, title)

    return ParsedPage(
        title=title,
        content=transformed_content,
        original_path=original_path,
        source_hash=source_hash,
    )


def _parse_csv_file(filepath: Path, original_path: str) -> ParsedPage | None:
    """
    Parse a Notion database CSV export.

    Args:
        filepath: Path to the CSV file.
        original_path: Original path relative to export root.

    Returns:
        ParsedPage with CSV content, or None if file couldn't be parsed.
    """
    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    title, source_hash = parse_notion_filename(filepath.name)

    return ParsedPage(
        title=title,
        content=content,
        original_path=original_path,
        source_hash=source_hash,
        filetype="csv",
    )


def transform_content(content: str) -> str:
    """
    Transform Notion-specific markdown to standard markdown.

    Handles:
    - Toggle blocks → nested bullet lists
    - Callouts (aside blocks) → blockquotes
    - Internal links (partial - full remapping done later)
    - Cleans up Notion-specific formatting
    - Preserves equations, code blocks, and tables

    Args:
        content: Raw markdown content from Notion export.

    Returns:
        Transformed markdown content.
    """
    if not content:
        return ""

    lines = content.split("\n")
    result_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Handle toggle blocks (Notion uses <details> tags)
        if line.strip().startswith("<details>"):
            toggle_lines, consumed = _transform_toggle_block(lines, i)
            result_lines.extend(toggle_lines)
            i += consumed
            continue

        # Handle callout/aside blocks (Notion exports these with <aside> tags)
        if line.strip().startswith("<aside>"):
            callout_lines, consumed = _transform_callout_block(lines, i)
            result_lines.extend(callout_lines)
            i += consumed
            continue

        # Clean up any remaining Notion-specific HTML
        line = _clean_notion_html(line)

        # Transform image paths if needed
        line = _transform_image_paths(line)

        result_lines.append(line)
        i += 1

    result = "\n".join(result_lines)

    # Clean up excessive blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


def _transform_toggle_block(lines: list[str], start_idx: int) -> tuple[list[str], int]:
    """
    Transform a Notion toggle block to a nested bullet list.

    Args:
        lines: All content lines.
        start_idx: Index where <details> tag starts.

    Returns:
        Tuple of (transformed lines, number of lines consumed).
    """
    result = []
    i = start_idx
    consumed = 0
    summary_text = ""
    content_lines = []
    in_details = True

    while i < len(lines) and in_details:
        line = lines[i]
        consumed += 1

        if "<summary>" in line and "</summary>" in line:
            # Extract summary text
            match = re.search(r"<summary>(.*?)</summary>", line)
            if match:
                summary_text = match.group(1).strip()
        elif "</details>" in line:
            in_details = False
        elif "<details>" not in line and "<summary>" not in line:
            # Content inside the toggle
            stripped = line.strip()
            if stripped:
                content_lines.append(stripped)

        i += 1

    # Convert to nested bullet list
    if summary_text:
        result.append(f"- {summary_text}")
        for content_line in content_lines:
            result.append(f"  - {content_line}")

    return result, consumed


def _transform_callout_block(lines: list[str], start_idx: int) -> tuple[list[str], int]:
    """
    Transform a Notion callout/aside block to a blockquote.

    Notion exports callouts as <aside> blocks with an emoji indicator.
    Format: <aside>emoji Content here</aside>

    Args:
        lines: All content lines.
        start_idx: Index where <aside> tag starts.

    Returns:
        Tuple of (transformed lines, number of lines consumed).
    """
    result = []
    i = start_idx
    consumed = 0
    content_lines = []
    in_aside = True

    while i < len(lines) and in_aside:
        line = lines[i]
        consumed += 1

        if "</aside>" in line:
            # Extract content before closing tag
            before_close = line.split("</aside>")[0]
            # Remove opening tag if on same line
            before_close = re.sub(r"<aside[^>]*>", "", before_close)
            if before_close.strip():
                content_lines.append(before_close.strip())
            in_aside = False
        elif "<aside" in line:
            # Opening tag - extract any content after it
            after_open = re.sub(r"<aside[^>]*>", "", line)
            if after_open.strip():
                content_lines.append(after_open.strip())
        else:
            # Content inside the aside
            stripped = line.strip()
            if stripped:
                content_lines.append(stripped)

        i += 1

    # Convert to blockquote
    for content_line in content_lines:
        result.append(f"> {content_line}")

    return result, consumed


def _transform_image_paths(line: str) -> str:
    """
    Transform image paths in markdown to be more portable.

    Notion exports may have relative paths to images in an 'images' folder
    or inline base64 data. This function handles:
    - Relative paths: keeps as-is (will need to be handled during import)
    - URL paths: preserves external URLs
    - Data URIs: preserves inline images

    Args:
        line: A single line of content.

    Returns:
        Line with transformed image paths.
    """
    # Pattern for markdown images: ![alt](path)
    # We keep the images as-is for now, but clean up any URL encoding issues
    def clean_image_path(match):
        alt = match.group(1)
        path = match.group(2)

        # Decode URL-encoded paths for readability
        # But preserve external URLs and data URIs
        if not path.startswith(("http://", "https://", "data:")):
            path = unquote(path)

        return f"![{alt}]({path})"

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", clean_image_path, line)


def _clean_notion_html(line: str) -> str:
    """
    Remove or convert Notion-specific HTML elements.

    Args:
        line: A single line of content.

    Returns:
        Cleaned line.
    """
    # Remove empty anchor tags (Notion uses these for block references)
    line = re.sub(r'<a\s+id="[^"]*"\s*/>', "", line)

    # Remove other empty HTML tags
    line = re.sub(r"<[^>]+/>", "", line)

    # Convert <br> to newlines
    line = line.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")

    return line


def _remove_duplicate_title(content: str, title: str) -> str:
    """
    Remove the first heading if it matches the page title.

    Notion often includes the page title as the first H1 heading,
    which is redundant since we store the title separately.

    Args:
        content: The markdown content.
        title: The page title.

    Returns:
        Content with duplicate title heading removed.
    """
    if not content:
        return content

    lines = content.split("\n")

    # Find first non-empty line
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        # Check if it's a heading that matches the title
        match = re.match(r"^#+\s+(.+)$", stripped)
        if match:
            heading_text = match.group(1).strip()
            if heading_text.lower() == title.lower():
                # Remove this line and any following blank lines
                remaining = lines[i + 1 :]
                while remaining and not remaining[0].strip():
                    remaining.pop(0)
                return "\n".join(remaining)

        # First non-empty line is not a matching heading, keep content as-is
        break

    return content


def extract_notion_links(content: str) -> list[tuple[str, str, str]]:
    """
    Extract internal Notion links from markdown content.

    Args:
        content: Markdown content to search.

    Returns:
        List of tuples: (full_match, link_text, link_target)
        where link_target is the relative path to another Notion page or database.
    """
    # Pattern for markdown links: [text](path)
    # Notion uses URL-encoded paths like: [Link](Other%20Page%20hash.md)
    # Also match .csv files for database links
    pattern = r"\[([^\]]+)\]\(([^)]+\.(?:md|csv))\)"

    matches = []
    for match in re.finditer(pattern, content):
        full_match = match.group(0)
        link_text = match.group(1)
        link_target = unquote(match.group(2))  # URL decode the path
        matches.append((full_match, link_text, link_target))

    return matches


def remap_links(content: str, id_mapping: dict[str, str]) -> str:
    """
    Replace Notion internal links with Hyperclast page links.

    Uses a single-pass positional replacement to avoid str.replace() pitfalls:
    - str.replace() replaces ALL occurrences, not just the intended one
    - If two links share a substring, an earlier replacement can corrupt a later match

    Args:
        content: Markdown content with Notion links.
        id_mapping: Dict mapping source_hash to hyperclast external_id.

    Returns:
        Content with remapped links.
    """
    pattern = r"\[([^\]]+)\]\(([^)]+\.(?:md|csv))\)"

    parts = []
    last_end = 0

    for match in re.finditer(pattern, content):
        link_text = match.group(1)
        link_target = unquote(match.group(2))

        # Extract the notion hash from the link target filename
        _, source_hash = parse_notion_filename(os.path.basename(link_target))

        if source_hash and source_hash in id_mapping:
            hyperclast_id = id_mapping[source_hash]
            new_link = f"[{link_text}](/pages/{hyperclast_id}/)"
            parts.append(content[last_end : match.start()])
            parts.append(new_link)
            last_end = match.end()
        # If hash not found, leave the link as-is (will be broken but preserved)

    if not parts:
        return content

    parts.append(content[last_end:])
    return "".join(parts)


def flatten_page_tree(pages: list[ParsedPage]) -> list[ParsedPage]:
    """
    Flatten a nested page tree into a single list.

    Preserves the original_path so hierarchy can be reconstructed if needed.

    Args:
        pages: Nested list of ParsedPage objects.

    Returns:
        Flat list of all ParsedPage objects.
    """
    result = []

    def flatten(page_list: list[ParsedPage]):
        for page in page_list:
            result.append(page)
            if page.children:
                flatten(page.children)

    flatten(pages)
    return result


def _is_index_only_page(parsed_page: ParsedPage) -> bool:
    """
    Detect whether a parent page is a pure index — its content is only
    links to child pages (and optional whitespace/blank lines).

    In Notion, a page that serves only as a container for child pages
    exports as a markdown file whose body is just a list of internal
    links like ``[Child](Child%20Page%20hash.md)``. When importing into
    Hyperclast, the folder already represents this navigational structure,
    so creating a duplicate page adds clutter without value.

    A page is considered index-only when:
    1. It has children (it's a parent page that maps to a folder).
    2. After removing all internal Notion links (`[text](*.md)` /
       `[text](*.csv)`), the remaining text is empty or whitespace-only.

    Args:
        parsed_page: A ParsedPage with children.

    Returns:
        True if the page content is purely navigational links.
    """
    if not parsed_page.children:
        return False

    content = parsed_page.content
    if not content or not content.strip():
        # Empty content with children — the folder alone is sufficient.
        return True

    # Strip all internal Notion links (markdown links to .md/.csv files).
    # These are the exact links that extract_notion_links() would find.
    stripped = re.sub(r"\[([^\]]+)\]\([^)]+\.(?:md|csv)\)", "", content)

    # If nothing meaningful remains, this is an index-only page.
    return not stripped.strip()


def _sanitize_folder_name(name: str) -> str:
    """
    Sanitize a folder name for use during import.

    Strips forbidden characters (/, \\, control chars) and truncates to
    MAX_FOLDER_NAME_LENGTH. Unlike validate_folder_name() which raises on
    invalid input, this silently cleans the name since import data comes
    from external sources.
    """
    from pages.services.folders import (
        CONTROL_CHARS_PATTERN,
        FORBIDDEN_CHARS_PATTERN,
        MAX_FOLDER_NAME_LENGTH,
    )

    if not name:
        return "Untitled"

    name = name.strip()
    name = FORBIDDEN_CHARS_PATTERN.sub("", name)
    name = CONTROL_CHARS_PATTERN.sub("", name)
    name = name.strip()

    if not name:
        return "Untitled"

    if len(name) > MAX_FOLDER_NAME_LENGTH:
        name = name[:MAX_FOLDER_NAME_LENGTH]

    return name


def _create_folders_from_tree(parsed_pages: list[ParsedPage], project, max_depth: int = 10) -> tuple[dict, set]:
    """
    Create Folder rows from the parsed page tree's directory structure.

    Walks the tree and creates folders for each level that has children.
    Respects max depth by flattening deeper directories into the deepest
    allowed level. Enforces MAX_FOLDERS_PER_PROJECT by flattening once
    the limit is reached. Sanitizes folder names to strip forbidden characters.

    Args:
        parsed_pages: Nested list of ParsedPage objects.
        project: Project instance.
        max_depth: Maximum folder nesting depth.

    Returns:
        Tuple of:
            - dict mapping id(parsed_page) -> Folder instance
            - set of Folder instances that were newly created (not reused)
    """
    from pages.models import Folder
    from pages.services.folders import MAX_FOLDERS_PER_PROJECT

    # Map: parsed_page id -> Folder instance
    page_folder_map = {}
    # Track only folders created by this import (not reused via get_or_create)
    created_folder_set = set()

    # Count existing folders to enforce limit
    existing_count = Folder.objects.filter(project=project).count()
    folders_created = 0
    limit_warned = False

    def process_level(pages, parent_folder, depth):
        nonlocal folders_created, limit_warned

        for page in pages:
            if page.children:
                # This page has children, so it acts as a "directory"
                # Check both depth limit and folder count limit
                if depth <= max_depth and (existing_count + folders_created) < MAX_FOLDERS_PER_PROJECT:
                    sanitized_name = _sanitize_folder_name(page.title)
                    folder, created = Folder.objects.get_or_create(
                        project=project,
                        parent=parent_folder,
                        name=sanitized_name,
                        defaults={},
                    )
                    if created:
                        folders_created += 1
                        created_folder_set.add(folder)
                elif not limit_warned and (existing_count + folders_created) >= MAX_FOLDERS_PER_PROJECT:
                    logger.warning(
                        f"Folder limit ({MAX_FOLDERS_PER_PROJECT}) reached for project "
                        f"{project.external_id} during import. Remaining directories "
                        f"will be flattened."
                    )
                    limit_warned = True
                    # Flatten into the deepest allowed folder
                    folder = parent_folder
                else:
                    # Depth exceeded or limit reached — flatten
                    folder = parent_folder

                # Parent page goes into its own folder (alongside children)
                page_folder_map[id(page)] = folder

                # For CSV databases, create a "{title} Rows" subfolder for
                # row pages so they don't mix with the CSV overview page.
                children_folder = folder
                if page.filetype == "csv" and folder is not None:
                    rows_depth = depth + 1
                    if rows_depth <= max_depth and (existing_count + folders_created) < MAX_FOLDERS_PER_PROJECT:
                        rows_name = _sanitize_folder_name(f"{page.title} Rows")
                        rows_folder, rows_created = Folder.objects.get_or_create(
                            project=project,
                            parent=folder,
                            name=rows_name,
                            defaults={},
                        )
                        if rows_created:
                            folders_created += 1
                            created_folder_set.add(rows_folder)
                        children_folder = rows_folder

                # Children go into this folder (or the Rows subfolder for CSVs)
                for child in page.children:
                    page_folder_map[id(child)] = children_folder

                # Recurse for nested children
                process_level(page.children, children_folder, depth + 1)

    process_level(parsed_pages, None, 1)
    return page_folder_map, created_folder_set


def _cleanup_empty_folders(folders: set) -> int:
    """
    Delete folders that have no pages and no subfolders.

    Processes bottom-up: deepest folders first, so that removing a leaf folder
    can make its parent eligible for removal in the same pass.

    Args:
        folders: Set of Folder instances to check.

    Returns:
        Number of folders deleted.
    """
    # Sort by depth (deepest first) so leaf folders are checked before parents.
    # Depth is determined by walking the parent chain.
    def _depth(folder):
        d = 0
        current = folder
        while current.parent_id is not None:
            d += 1
            current = current.parent
        return d

    sorted_folders = sorted(folders, key=_depth, reverse=True)

    deleted = 0
    deleted_ids = set()
    for folder in sorted_folders:
        if folder.pk in deleted_ids:
            continue
        has_pages = folder.pages.exists()
        # Exclude already-deleted subfolders from the check
        has_subfolders = folder.subfolders.exclude(pk__in=deleted_ids).exists()
        if not has_pages and not has_subfolders:
            deleted_ids.add(folder.pk)
            folder.delete()
            deleted += 1

    return deleted


def create_import_pages(parsed_pages: list[ParsedPage], project, user, import_job=None):
    """
    Orchestrate the creation of pages from parsed Notion export.

    This function handles:
    1. Creating folders from the directory structure
    2. Flattening the page tree
    3. Checking for duplicate source_hash values already in the project
    4. Creating new pages in batch (skipping duplicates)
    5. Building source_hash → hyperclast_id mapping (includes existing pages)
    6. Second pass: updating each page's content with remapped links
    7. Syncing PageLink records for all pages
    8. Creating ImportedPage records to track the import

    Args:
        parsed_pages: List of ParsedPage objects (possibly nested)
        project: Project instance to create pages in
        user: User who will own the pages
        import_job: Optional ImportJob instance for tracking

    Returns:
        dict with:
            - pages: List of created Page instances
            - id_mapping: Dict mapping source_hash → external_id
            - stats: Dict with import statistics (total, created, skipped, failed)
    """
    from django.db import transaction

    from imports.models import ImportedPage
    from pages.models import Page
    from pages.models.links import PageLink

    # Step 0: Create folders from the directory structure
    page_folder_map, created_folders = _create_folders_from_tree(parsed_pages, project)

    # Step 1: Flatten the page tree
    flat_pages = flatten_page_tree(parsed_pages)

    if not flat_pages:
        return {
            "pages": [],
            "id_mapping": {},
            "stats": {"total": 0, "created": 0, "skipped": 0, "failed": 0},
        }

    # Step 2: Collect all source_hashes we need to look up:
    # - Hashes of pages being imported (for deduplication)
    # - Hashes referenced in links within content (for link remapping)
    incoming_hashes = {p.source_hash for p in flat_pages if p.source_hash}

    # Extract hashes from links in content
    linked_hashes = set()
    for parsed_page in flat_pages:
        links = extract_notion_links(parsed_page.content)
        for _, _, link_target in links:
            _, link_hash = parse_notion_filename(os.path.basename(link_target))
            if link_hash:
                linked_hashes.add(link_hash)

    all_hashes_to_lookup = incoming_hashes | linked_hashes

    # Query existing pages by these hashes
    existing_imports = (
        ImportedPage.objects.filter(
            project=project,
            source_hash__in=all_hashes_to_lookup,
        )
        .select_related("page")
        .values("source_hash", "page__external_id")
    )

    # Build mapping of existing hashes to their page external_ids
    existing_hash_map = {imp["source_hash"]: str(imp["page__external_id"]) for imp in existing_imports}

    # Build set of hashes that already exist as imported pages (for deduplication)
    existing_page_hashes = {imp["source_hash"] for imp in existing_imports if imp["source_hash"] in incoming_hashes}

    # Step 3: Prepare page data for batch creation (skip duplicates)
    pages_data = []
    pages_to_create = []  # Track which parsed_pages will be created
    skipped_count = 0

    for parsed_page in flat_pages:
        # Skip if this page's source_hash already exists in the project
        # (Only check against incoming_hashes, not linked hashes)
        if parsed_page.source_hash and parsed_page.source_hash in existing_page_hashes:
            skipped_count += 1
            continue

        # Skip index-only parent pages — their folder already represents
        # the navigational structure, so creating a duplicate page with
        # the same name adds clutter without value.
        if _is_index_only_page(parsed_page):
            skipped_count += 1
            continue

        page_data = {
            "title": parsed_page.title or "Untitled",
            "content": parsed_page.content,
            "source_hash": parsed_page.source_hash,
            "original_path": parsed_page.original_path,
            "filetype": parsed_page.filetype,
        }

        # Assign folder from the tree structure
        folder = page_folder_map.get(id(parsed_page))
        if folder:
            page_data["folder"] = folder

        pages_data.append(page_data)
        pages_to_create.append(parsed_page)

    # Step 4: Create new pages in a single transaction
    created_pages = []
    if pages_data:
        with transaction.atomic():
            created_pages = Page.objects.create_batch(pages_data, project, user)

    # Step 5: Build source_hash → external_id mapping
    # Include BOTH existing pages (for link remapping) and newly created pages
    id_mapping = dict(existing_hash_map)  # Start with existing
    for page in created_pages:
        if page._source_hash:
            id_mapping[page._source_hash] = str(page.external_id)

    # Step 6: Second pass - remap internal links in new pages
    pages_to_update = []
    for page in created_pages:
        content = page.details.get("content", "")
        if content:
            remapped_content = remap_links(content, id_mapping)
            if remapped_content != content:
                page.details["content"] = remapped_content
                pages_to_update.append(page)

    # Bulk update pages with remapped links
    if pages_to_update:
        with transaction.atomic():
            Page.objects.bulk_update(pages_to_update, ["details"])

    # Step 7: Sync PageLink records for all new pages
    for page in created_pages:
        try:
            content = page.details.get("content", "")
            PageLink.objects.sync_links_for_page(page, content)
        except Exception as e:
            # Don't fail the entire import if link sync fails for one page
            logger.warning(f"Failed to sync links for page {page.external_id}: {e}")

    # Step 8: Create ImportedPage records if import_job provided
    if import_job and created_pages:
        imported_pages = []
        for page, parsed_page in zip(created_pages, pages_to_create):
            imported_pages.append(
                ImportedPage(
                    import_job=import_job,
                    project=project,
                    page=page,
                    original_path=parsed_page.original_path,
                    source_hash=parsed_page.source_hash,
                )
            )

        with transaction.atomic():
            ImportedPage.objects.bulk_create(imported_pages)

    # Step 9: Clean up empty folders created during this import
    # A folder can end up empty if all its pages were skipped (duplicates or
    # index-only parents). Only clean up folders that were newly created by
    # this import — never delete pre-existing folders that were merely reused
    # via get_or_create.
    if created_folders:
        _cleanup_empty_folders(created_folders)

    return {
        "pages": created_pages,
        "id_mapping": id_mapping,
        "stats": {
            "total": len(flat_pages),
            "created": len(created_pages),
            "skipped": skipped_count,
            "failed": 0,
        },
    }

"""
Tests for the Notion export parser service.
"""

import io
import shutil
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from imports.constants import NOTION_NESTED_ZIP_PATTERN
from imports.exceptions import (
    ImportExtractedSizeExceededError,
    ImportExtractionTimeoutError,
    ImportInvalidZipError,
    ImportNestedArchiveError,
)
from imports.services.notion import (
    ParsedPage,
    _clean_notion_html,
    _extract_nested_zips,
    _find_child_directory,
    _is_safe_path,
    _parse_csv_file,
    _remove_duplicate_title,
    _transform_callout_block,
    _transform_image_paths,
    _transform_toggle_block,
    build_page_tree,
    extract_notion_links,
    extract_zip,
    extract_zip_safely,
    flatten_page_tree,
    parse_markdown_file,
    parse_notion_filename,
    remap_links,
    transform_content,
)


class TestParseNotionFilename(TestCase):
    """Tests for parse_notion_filename()."""

    def test_parse_filename_with_hash(self):
        """Parses filename with 32-char hash correctly."""
        title, hash_val = parse_notion_filename("My Notes abc123def456789012345678901234.md")
        self.assertEqual(title, "My Notes")
        self.assertEqual(hash_val, "abc123def456789012345678901234")

    def test_parse_filename_with_16_char_hash(self):
        """Parses filename with 16-char hash correctly."""
        title, hash_val = parse_notion_filename("Meeting 2024-01-15 deadbeef12345678.md")
        self.assertEqual(title, "Meeting 2024-01-15")
        self.assertEqual(hash_val, "deadbeef12345678")

    def test_parse_filename_without_hash(self):
        """Handles filename without hash."""
        title, hash_val = parse_notion_filename("Simple Page.md")
        self.assertEqual(title, "Simple Page")
        self.assertEqual(hash_val, "")

    def test_parse_filename_csv(self):
        """Handles CSV files correctly."""
        title, hash_val = parse_notion_filename("Database Export abc123def456789012.csv")
        self.assertEqual(title, "Database Export")
        self.assertEqual(hash_val, "abc123def456789012")

    def test_parse_filename_unicode(self):
        """Handles Unicode characters in title."""
        title, hash_val = parse_notion_filename("日本語ページ abc123def456789012345678901234.md")
        self.assertEqual(title, "日本語ページ")
        self.assertEqual(hash_val, "abc123def456789012345678901234")

    def test_parse_filename_with_numbers_in_title(self):
        """Numbers in title are not confused with hash."""
        title, hash_val = parse_notion_filename("Meeting 2024 Notes abc123def456789012.md")
        self.assertEqual(title, "Meeting 2024 Notes")
        self.assertEqual(hash_val, "abc123def456789012")

    def test_parse_filename_short_hash_ignored(self):
        """Hash shorter than 16 chars is ignored."""
        title, hash_val = parse_notion_filename("Page abc123.md")
        self.assertEqual(title, "Page abc123")
        self.assertEqual(hash_val, "")

    def test_parse_filename_uppercase_hash(self):
        """Handles uppercase hex characters in hash."""
        title, hash_val = parse_notion_filename("Page ABCDEF1234567890.md")
        self.assertEqual(title, "Page")
        self.assertEqual(hash_val, "ABCDEF1234567890")

    def test_parse_filename_whitespace_handling(self):
        """Strips whitespace from title."""
        title, hash_val = parse_notion_filename("  Spaced Title  abc123def456789012.md")
        self.assertEqual(title, "Spaced Title")
        self.assertEqual(hash_val, "abc123def456789012")

    def test_parse_filename_empty_title(self):
        """Handles edge case of hash-only filename (with space prefix)."""
        # This is an unusual but valid case - a space followed by hash
        title, hash_val = parse_notion_filename(" abc123def456789012345678901234.md")
        self.assertEqual(title, "")
        self.assertEqual(hash_val, "abc123def456789012345678901234")


class TestFindChildDirectory(TestCase):
    """Tests for _find_child_directory()."""

    def test_finds_title_only_folder(self):
        """Finds folder using title only (actual Notion export format)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            title_dir = tmppath / "Test Pages"
            title_dir.mkdir()

            result = _find_child_directory(
                tmppath,
                stem="Test Pages 2e3fd10b505a80219203dfbe1efb387f",
                title="Test Pages",
            )

            self.assertEqual(result, title_dir)

    def test_finds_stem_folder_as_fallback(self):
        """Falls back to stem (title+hash) folder if title folder doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            stem_dir = tmppath / "Test Pages 2e3fd10b505a80219203dfbe1efb387f"
            stem_dir.mkdir()

            result = _find_child_directory(
                tmppath,
                stem="Test Pages 2e3fd10b505a80219203dfbe1efb387f",
                title="Test Pages",
            )

            self.assertEqual(result, stem_dir)

    def test_prefers_title_over_stem(self):
        """Prefers title-only folder when both exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            title_dir = tmppath / "Test Pages"
            title_dir.mkdir()
            stem_dir = tmppath / "Test Pages 2e3fd10b505a80219203dfbe1efb387f"
            stem_dir.mkdir()

            result = _find_child_directory(
                tmppath,
                stem="Test Pages 2e3fd10b505a80219203dfbe1efb387f",
                title="Test Pages",
            )

            # Should prefer title-only
            self.assertEqual(result, title_dir)

    def test_returns_none_when_no_folder_exists(self):
        """Returns None when no matching folder exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            result = _find_child_directory(
                tmppath,
                stem="Test Pages 2e3fd10b505a80219203dfbe1efb387f",
                title="Test Pages",
            )

            self.assertIsNone(result)

    def test_ignores_files_with_matching_names(self):
        """Only matches directories, not files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Create a file, not a directory
            (tmppath / "Test Pages").write_text("not a directory")

            result = _find_child_directory(
                tmppath,
                stem="Test Pages 2e3fd10b505a80219203dfbe1efb387f",
                title="Test Pages",
            )

            self.assertIsNone(result)


class TestExtractZip(TestCase):
    """Tests for extract_zip()."""

    def test_extract_valid_zip(self):
        """Extracts valid zip file successfully."""
        # Create a valid zip in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("test.md", "# Test Page\n\nContent here.")
        zip_buffer.seek(0)

        try:
            extracted_path = extract_zip(zip_buffer)
            self.assertTrue(extracted_path.exists())
            self.assertTrue((extracted_path / "test.md").exists())
            content = (extracted_path / "test.md").read_text()
            self.assertEqual(content, "# Test Page\n\nContent here.")
        finally:
            # Cleanup
            import shutil

            if extracted_path.exists():
                shutil.rmtree(extracted_path)

    def test_extract_invalid_zip(self):
        """Raises ImportInvalidZipError for invalid zip."""
        invalid_buffer = io.BytesIO(b"not a zip file")

        with self.assertRaises(ImportInvalidZipError):
            extract_zip(invalid_buffer)

    def test_extract_zip_path_traversal_absolute(self):
        """Rejects zip with absolute paths (security check)."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            # Create a malicious entry with absolute path
            info = zipfile.ZipInfo("/etc/passwd")
            zf.writestr(info, "malicious content")
        zip_buffer.seek(0)

        with self.assertRaises(ImportInvalidZipError) as ctx:
            extract_zip(zip_buffer)
        self.assertIn("Unsafe path", str(ctx.exception))

    def test_extract_zip_path_traversal_relative(self):
        """Rejects zip with path traversal attempts."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            info = zipfile.ZipInfo("../../../etc/passwd")
            zf.writestr(info, "malicious content")
        zip_buffer.seek(0)

        with self.assertRaises(ImportInvalidZipError) as ctx:
            extract_zip(zip_buffer)
        self.assertIn("Unsafe path", str(ctx.exception))

    def test_extract_zip_to_specified_path(self):
        """Extracts to specified path when provided."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("test.md", "content")
        zip_buffer.seek(0)

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = Path(tmpdir) / "extract_here"
            target_path.mkdir()

            extracted_path = extract_zip(zip_buffer, target_path)
            self.assertEqual(extracted_path, target_path)
            self.assertTrue((target_path / "test.md").exists())

    def test_extract_zip_nested_structure(self):
        """Handles nested directory structure."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("root.md", "# Root")
            zf.writestr("folder/child.md", "# Child")
            zf.writestr("folder/subfolder/grandchild.md", "# Grandchild")
        zip_buffer.seek(0)

        import shutil

        extracted_path = None
        try:
            extracted_path = extract_zip(zip_buffer)
            self.assertTrue((extracted_path / "root.md").exists())
            self.assertTrue((extracted_path / "folder" / "child.md").exists())
            self.assertTrue((extracted_path / "folder" / "subfolder" / "grandchild.md").exists())
        finally:
            if extracted_path and extracted_path.exists():
                shutil.rmtree(extracted_path)

    def test_extract_zip_with_nested_zip(self):
        """Extracts nested zip files (Notion block exports)."""
        # Create inner zip with actual content
        inner_zip = io.BytesIO()
        with zipfile.ZipFile(inner_zip, "w") as zf:
            zf.writestr("Test Page abc123def456789012.md", "# Test\n\nContent")
            zf.writestr("Test Page abc123def456789012/Child def456abc789012345.md", "# Child")
        inner_zip.seek(0)

        # Create outer zip containing the inner zip
        outer_zip = io.BytesIO()
        with zipfile.ZipFile(outer_zip, "w") as zf:
            zf.writestr("ExportBlock-uuid-Part-1.zip", inner_zip.getvalue())
        outer_zip.seek(0)

        extracted_path = None
        try:
            extracted_path = extract_zip(outer_zip)
            # The nested zip should be extracted, not left as a file
            self.assertFalse((extracted_path / "ExportBlock-uuid-Part-1.zip").exists())
            # The actual content should be accessible
            self.assertTrue((extracted_path / "Test Page abc123def456789012.md").exists())
            self.assertTrue((extracted_path / "Test Page abc123def456789012" / "Child def456abc789012345.md").exists())
        finally:
            if extracted_path and extracted_path.exists():
                shutil.rmtree(extracted_path)

    def test_extract_zip_with_multiple_nested_zips(self):
        """Extracts multiple nested zip files (multi-part exports)."""
        # Create first inner zip
        inner_zip1 = io.BytesIO()
        with zipfile.ZipFile(inner_zip1, "w") as zf:
            zf.writestr("Page One abc123def456789012.md", "# Page One")
        inner_zip1.seek(0)

        # Create second inner zip
        inner_zip2 = io.BytesIO()
        with zipfile.ZipFile(inner_zip2, "w") as zf:
            zf.writestr("Page Two def456abc789012345.md", "# Page Two")
        inner_zip2.seek(0)

        # Create outer zip containing both inner zips
        outer_zip = io.BytesIO()
        with zipfile.ZipFile(outer_zip, "w") as zf:
            zf.writestr("ExportBlock-uuid-Part-1.zip", inner_zip1.getvalue())
            zf.writestr("ExportBlock-uuid-Part-2.zip", inner_zip2.getvalue())
        outer_zip.seek(0)

        extracted_path = None
        try:
            extracted_path = extract_zip(outer_zip)
            # Both nested zips should be extracted
            self.assertTrue((extracted_path / "Page One abc123def456789012.md").exists())
            self.assertTrue((extracted_path / "Page Two def456abc789012345.md").exists())
        finally:
            if extracted_path and extracted_path.exists():
                shutil.rmtree(extracted_path)

    def test_extract_zip_mixed_content_preserves_zips(self):
        """Does not extract nested zips when mixed with other content."""
        # Create inner zip
        inner_zip = io.BytesIO()
        with zipfile.ZipFile(inner_zip, "w") as zf:
            zf.writestr("nested.md", "# Nested")
        inner_zip.seek(0)

        # Create outer zip with both a zip file and a markdown file
        outer_zip = io.BytesIO()
        with zipfile.ZipFile(outer_zip, "w") as zf:
            zf.writestr("readme.md", "# Readme")
            zf.writestr("archive.zip", inner_zip.getvalue())
        outer_zip.seek(0)

        extracted_path = None
        try:
            extracted_path = extract_zip(outer_zip)
            # The markdown should exist
            self.assertTrue((extracted_path / "readme.md").exists())
            # The zip should NOT be extracted (mixed content)
            self.assertTrue((extracted_path / "archive.zip").exists())
            # The nested content should NOT be extracted
            self.assertFalse((extracted_path / "nested.md").exists())
        finally:
            if extracted_path and extracted_path.exists():
                shutil.rmtree(extracted_path)


class TestBuildPageTree(TestCase):
    """Tests for build_page_tree()."""

    def test_build_tree_single_file(self):
        """Builds tree from single markdown file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "Test Page abc123def456789012.md").write_text("# Test\n\nContent")

            pages = build_page_tree(tmppath)

            self.assertEqual(len(pages), 1)
            self.assertEqual(pages[0].title, "Test Page")
            self.assertEqual(pages[0].source_hash, "abc123def456789012")

    def test_build_tree_nested_structure(self):
        """Builds tree with parent-child relationships."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create parent page
            (tmppath / "Parent Page abc123def456789012.md").write_text("# Parent\n\nParent content")

            # Create matching child directory
            child_dir = tmppath / "Parent Page abc123def456789012"
            child_dir.mkdir()
            (child_dir / "Child Page def456abc789012345.md").write_text("# Child\n\nChild content")

            pages = build_page_tree(tmppath)

            self.assertEqual(len(pages), 1)
            parent = pages[0]
            self.assertEqual(parent.title, "Parent Page")
            self.assertEqual(len(parent.children), 1)
            self.assertEqual(parent.children[0].title, "Child Page")

    def test_build_tree_nested_structure_title_only_folder(self):
        """Builds tree when folder uses title-only name (actual Notion export format)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create parent page with hash in filename
            (tmppath / "Test Pages 2e3fd10b505a80219203dfbe1efb387f.md").write_text("# Test Pages\n\nParent content")

            # Create matching child directory using TITLE ONLY (no hash)
            # This is the actual Notion export format
            child_dir = tmppath / "Test Pages"
            child_dir.mkdir()
            (child_dir / "Welcome 2e3fd10b505a808993f3e1bb9965b2e3.md").write_text("# Welcome")
            (child_dir / "Simple Notes 2e3fd10b505a806fa3b3f9538009acd0.md").write_text("# Simple Notes")

            pages = build_page_tree(tmppath)

            self.assertEqual(len(pages), 1)
            parent = pages[0]
            self.assertEqual(parent.title, "Test Pages")
            self.assertEqual(len(parent.children), 2)
            child_titles = {c.title for c in parent.children}
            self.assertEqual(child_titles, {"Welcome", "Simple Notes"})

    def test_build_tree_deeply_nested_title_only_folders(self):
        """Handles deeply nested structure with title-only folders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Root page
            (tmppath / "Root abc123def456789012.md").write_text("# Root")

            # First level child directory (title only)
            level1_dir = tmppath / "Root"
            level1_dir.mkdir()
            (level1_dir / "Level1 def456abc789012345.md").write_text("# Level1")

            # Second level child directory (title only)
            level2_dir = level1_dir / "Level1"
            level2_dir.mkdir()
            (level2_dir / "Level2 aabbccddeeff00112.md").write_text("# Level2")

            pages = build_page_tree(tmppath)

            self.assertEqual(len(pages), 1)
            root = pages[0]
            self.assertEqual(root.title, "Root")
            self.assertEqual(len(root.children), 1)

            level1 = root.children[0]
            self.assertEqual(level1.title, "Level1")
            self.assertEqual(len(level1.children), 1)

            level2 = level1.children[0]
            self.assertEqual(level2.title, "Level2")
            self.assertEqual(level2.children, [])

    def test_build_tree_multiple_top_level(self):
        """Handles multiple top-level pages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "Page A abc123def456789012.md").write_text("# A")
            (tmppath / "Page B def456abc789012345.md").write_text("# B")
            (tmppath / "Page C aabbccddeeff00112.md").write_text("# C")

            pages = build_page_tree(tmppath)

            self.assertEqual(len(pages), 3)
            titles = [p.title for p in pages]
            self.assertIn("Page A", titles)
            self.assertIn("Page B", titles)
            self.assertIn("Page C", titles)

    def test_build_tree_includes_csv(self):
        """Includes CSV database exports with correct filetype."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "Database abc123def456789012.csv").write_text("Name,Value\nFoo,Bar")

            pages = build_page_tree(tmppath)

            self.assertEqual(len(pages), 1)
            self.assertEqual(pages[0].title, "Database")
            self.assertIn("Name,Value", pages[0].content)
            self.assertEqual(pages[0].filetype, "csv")

    def test_build_tree_skips_all_csv_variant(self):
        """Skips _all.csv files (Notion exports both {name}.csv and {name}_all.csv)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Notion exports both variants - we should only import the regular one
            (tmppath / "Database abc123def456789012.csv").write_text("Name,Value\nFoo,Bar")
            (tmppath / "Database abc123def456789012_all.csv").write_text("Name,Value,Hidden\nFoo,Bar,Secret")

            pages = build_page_tree(tmppath)

            # Should only have one CSV (not the _all variant)
            self.assertEqual(len(pages), 1)
            self.assertEqual(pages[0].title, "Database")
            # Should be the regular CSV, not the _all variant
            self.assertNotIn("Hidden", pages[0].content)
            self.assertNotIn("Secret", pages[0].content)

    def test_build_tree_empty_directory(self):
        """Handles empty directory gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pages = build_page_tree(Path(tmpdir))
            self.assertEqual(pages, [])

    def test_build_tree_ignores_non_md_files(self):
        """Ignores non-markdown files (except CSV)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "page.md").write_text("# Valid")
            (tmppath / "image.png").write_bytes(b"fake image")
            (tmppath / "document.pdf").write_bytes(b"fake pdf")

            pages = build_page_tree(tmppath)

            self.assertEqual(len(pages), 1)
            self.assertEqual(pages[0].title, "page")


class TestParseMarkdownFile(TestCase):
    """Tests for parse_markdown_file()."""

    def test_parse_basic_file(self):
        """Parses basic markdown file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "My Notes abc123def456789012.md"
            filepath.write_text("# My Notes\n\nSome content here.")

            result = parse_markdown_file(filepath, "My Notes abc123def456789012.md")

            self.assertIsNotNone(result)
            self.assertEqual(result.title, "My Notes")
            self.assertEqual(result.source_hash, "abc123def456789012")
            self.assertEqual(result.original_path, "My Notes abc123def456789012.md")
            self.assertEqual(result.filetype, "md")
            # Duplicate title heading should be removed
            self.assertNotIn("# My Notes", result.content)
            self.assertIn("Some content here", result.content)

    def test_parse_file_preserves_content(self):
        """Preserves non-duplicate heading content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "Page abc123def456789012.md"
            content = "# Page\n\n## Section 1\n\nParagraph.\n\n## Section 2\n\nMore content."
            filepath.write_text(content)

            result = parse_markdown_file(filepath, "Page abc123def456789012.md")

            self.assertIn("## Section 1", result.content)
            self.assertIn("## Section 2", result.content)
            self.assertIn("Paragraph", result.content)

    def test_parse_file_unicode(self):
        """Handles Unicode content correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "日本語 abc123def456789012.md"
            filepath.write_text("# 日本語\n\nこれは日本語のテストです。", encoding="utf-8")

            result = parse_markdown_file(filepath, "日本語 abc123def456789012.md")

            self.assertEqual(result.title, "日本語")
            self.assertIn("日本語のテスト", result.content)

    def test_parse_file_not_found(self):
        """Returns None for non-existent file."""
        result = parse_markdown_file(Path("/nonexistent/path.md"), "path.md")
        self.assertIsNone(result)


class TestParseCsvFile(TestCase):
    """Tests for _parse_csv_file()."""

    def test_parse_basic_csv(self):
        """Parses basic CSV file with correct filetype."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "Database abc123def456789012.csv"
            filepath.write_text("Name,Status,Priority\nTask 1,Done,High\nTask 2,In Progress,Low")

            result = _parse_csv_file(filepath, "Database abc123def456789012.csv")

            self.assertIsNotNone(result)
            self.assertEqual(result.title, "Database")
            self.assertEqual(result.source_hash, "abc123def456789012")
            self.assertEqual(result.original_path, "Database abc123def456789012.csv")
            self.assertEqual(result.filetype, "csv")
            self.assertIn("Name,Status,Priority", result.content)
            self.assertIn("Task 1,Done,High", result.content)

    def test_parse_csv_preserves_content(self):
        """Preserves CSV content exactly (no transformation)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "Export abc123def456789012.csv"
            csv_content = '"Title","Notes","Tags"\n"Item with, comma","Some notes","tag1,tag2"'
            filepath.write_text(csv_content)

            result = _parse_csv_file(filepath, "Export abc123def456789012.csv")

            # CSV content should be preserved exactly
            self.assertEqual(result.content, csv_content)
            self.assertEqual(result.filetype, "csv")

    def test_parse_csv_unicode(self):
        """Handles Unicode content in CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "データベース abc123def456789012.csv"
            filepath.write_text("名前,状態\nタスク,完了", encoding="utf-8")

            result = _parse_csv_file(filepath, "データベース abc123def456789012.csv")

            self.assertEqual(result.title, "データベース")
            self.assertIn("名前,状態", result.content)
            self.assertEqual(result.filetype, "csv")

    def test_parse_csv_not_found(self):
        """Returns None for non-existent file."""
        result = _parse_csv_file(Path("/nonexistent/path.csv"), "path.csv")
        self.assertIsNone(result)


class TestTransformContent(TestCase):
    """Tests for transform_content()."""

    def test_transform_empty_content(self):
        """Handles empty content."""
        result = transform_content("")
        self.assertEqual(result, "")

    def test_transform_plain_markdown(self):
        """Leaves plain markdown unchanged."""
        content = "# Heading\n\nParagraph text.\n\n- List item"
        result = transform_content(content)

        self.assertIn("# Heading", result)
        self.assertIn("Paragraph text", result)
        self.assertIn("- List item", result)

    def test_transform_toggle_block(self):
        """Transforms toggle block to nested list."""
        content = """Some text.

<details>
<summary>Toggle Header</summary>

Content inside toggle.

More content.

</details>

After toggle."""

        result = transform_content(content)

        self.assertIn("- Toggle Header", result)
        self.assertIn("  - Content inside toggle", result)
        self.assertNotIn("<details>", result)
        self.assertNotIn("</details>", result)

    def test_transform_removes_empty_anchors(self):
        """Removes Notion's empty anchor tags."""
        content = 'Text with <a id="block-abc123"/> anchor tags.'
        result = transform_content(content)

        self.assertNotIn("<a id=", result)
        self.assertIn("Text with", result)
        self.assertIn("anchor tags", result)

    def test_transform_converts_br_tags(self):
        """Converts <br> tags to newlines."""
        content = "Line one<br>Line two<br/>Line three<br />Line four"
        result = transform_content(content)

        self.assertNotIn("<br", result)

    def test_transform_cleans_excessive_blank_lines(self):
        """Reduces multiple blank lines to double."""
        content = "Paragraph one.\n\n\n\n\nParagraph two."
        result = transform_content(content)

        self.assertNotIn("\n\n\n", result)
        self.assertIn("Paragraph one.", result)
        self.assertIn("Paragraph two.", result)


class TestTransformToggleBlock(TestCase):
    """Tests for _transform_toggle_block()."""

    def test_toggle_basic(self):
        """Transforms basic toggle block."""
        lines = [
            "<details>",
            "<summary>Click to expand</summary>",
            "",
            "Hidden content.",
            "",
            "</details>",
        ]

        result, consumed = _transform_toggle_block(lines, 0)

        self.assertEqual(consumed, 6)
        self.assertEqual(result[0], "- Click to expand")
        self.assertEqual(result[1], "  - Hidden content.")

    def test_toggle_multiple_content_lines(self):
        """Handles multiple content lines in toggle."""
        lines = [
            "<details>",
            "<summary>Header</summary>",
            "Line 1",
            "Line 2",
            "Line 3",
            "</details>",
        ]

        result, consumed = _transform_toggle_block(lines, 0)

        self.assertEqual(len(result), 4)  # Header + 3 content lines
        self.assertEqual(result[0], "- Header")

    def test_toggle_empty_content(self):
        """Handles toggle with no content."""
        lines = [
            "<details>",
            "<summary>Empty Toggle</summary>",
            "</details>",
        ]

        result, consumed = _transform_toggle_block(lines, 0)

        self.assertEqual(result, ["- Empty Toggle"])


class TestCleanNotionHtml(TestCase):
    """Tests for _clean_notion_html()."""

    def test_removes_anchor_ids(self):
        """Removes anchor ID tags."""
        line = 'Text <a id="abc123"/> more text'
        result = _clean_notion_html(line)
        self.assertEqual(result, "Text  more text")

    def test_removes_self_closing_tags(self):
        """Removes self-closing HTML tags."""
        line = "Before <br/> after"
        result = _clean_notion_html(line)
        self.assertIn("Before", result)
        self.assertIn("after", result)

    def test_preserves_regular_content(self):
        """Preserves non-HTML content."""
        line = "Regular markdown **bold** text"
        result = _clean_notion_html(line)
        self.assertEqual(result, "Regular markdown **bold** text")


class TestRemoveDuplicateTitle(TestCase):
    """Tests for _remove_duplicate_title()."""

    def test_removes_matching_h1(self):
        """Removes H1 that matches title."""
        content = "# My Page Title\n\nContent here."
        result = _remove_duplicate_title(content, "My Page Title")
        self.assertNotIn("# My Page Title", result)
        self.assertIn("Content here", result)

    def test_removes_matching_h2(self):
        """Removes H2 that matches title."""
        content = "## My Page Title\n\nContent here."
        result = _remove_duplicate_title(content, "My Page Title")
        self.assertNotIn("## My Page Title", result)

    def test_preserves_non_matching_heading(self):
        """Preserves heading that doesn't match title."""
        content = "# Different Heading\n\nContent here."
        result = _remove_duplicate_title(content, "My Page Title")
        self.assertIn("# Different Heading", result)

    def test_case_insensitive_match(self):
        """Matches title case-insensitively."""
        content = "# MY PAGE TITLE\n\nContent here."
        result = _remove_duplicate_title(content, "My Page Title")
        self.assertNotIn("# MY PAGE TITLE", result)

    def test_handles_empty_content(self):
        """Handles empty content."""
        result = _remove_duplicate_title("", "Title")
        self.assertEqual(result, "")

    def test_removes_following_blank_lines(self):
        """Removes blank lines after duplicate title."""
        content = "# Title\n\n\n\nContent here."
        result = _remove_duplicate_title(content, "Title")
        self.assertNotIn("\n\n\n", result)
        self.assertIn("Content here", result)


class TestExtractNotionLinks(TestCase):
    """Tests for extract_notion_links()."""

    def test_extract_simple_link(self):
        """Extracts simple markdown link to .md file."""
        content = "See [Other Page](Other%20Page%20abc123def456789012.md) for details."
        links = extract_notion_links(content)

        self.assertEqual(len(links), 1)
        full_match, text, target = links[0]
        self.assertEqual(text, "Other Page")
        self.assertEqual(target, "Other Page abc123def456789012.md")

    def test_extract_multiple_links(self):
        """Extracts multiple links from content."""
        content = """
        Link to [Page A](Page%20A%20abc123.md) and [Page B](Page%20B%20def456.md).
        Also see [Page C](folder/Page%20C%20ghi789.md).
        """
        links = extract_notion_links(content)

        self.assertEqual(len(links), 3)

    def test_extract_url_encoded_path(self):
        """Decodes URL-encoded paths."""
        content = "[My Notes](My%20Notes%20With%20Spaces%20abc123def456789012.md)"
        links = extract_notion_links(content)

        self.assertEqual(len(links), 1)
        _, _, target = links[0]
        self.assertEqual(target, "My Notes With Spaces abc123def456789012.md")

    def test_ignores_external_links(self):
        """Ignores links to non-.md targets."""
        content = "[External](https://example.com) and [Image](image.png)"
        links = extract_notion_links(content)

        self.assertEqual(len(links), 0)

    def test_extracts_nested_path_links(self):
        """Extracts links with folder paths."""
        content = "[Child](Parent/Child%20abc123def456789012.md)"
        links = extract_notion_links(content)

        self.assertEqual(len(links), 1)
        _, _, target = links[0]
        self.assertIn("Parent/Child", target)

    def test_extract_csv_link(self):
        """Extracts links to CSV database files."""
        content = "[Task Database](Database%20&%20Table/Task%20Database%20abc123def456789012.csv)"
        links = extract_notion_links(content)

        self.assertEqual(len(links), 1)
        full_match, text, target = links[0]
        self.assertEqual(text, "Task Database")
        self.assertEqual(target, "Database & Table/Task Database abc123def456789012.csv")

    def test_extract_mixed_md_and_csv_links(self):
        """Extracts both .md and .csv links from content."""
        content = """
        [Page](Page%20abc123def456789012.md)
        [Database](Database%20def456abc789012345.csv)
        """
        links = extract_notion_links(content)

        self.assertEqual(len(links), 2)
        targets = [link[2] for link in links]
        self.assertTrue(any(".md" in t for t in targets))
        self.assertTrue(any(".csv" in t for t in targets))


class TestRemapLinks(TestCase):
    """Tests for remap_links()."""

    def test_remap_single_link(self):
        """Remaps single Notion link to Hyperclast link."""
        content = "See [Other Page](Other%20Page%20abc123def456789012.md) for details."
        id_mapping = {"abc123def456789012": "uuid-1234-5678"}

        result = remap_links(content, id_mapping)

        self.assertIn("[Other Page](/pages/uuid-1234-5678/)", result)
        self.assertNotIn(".md", result)

    def test_remap_multiple_links(self):
        """Remaps multiple links correctly."""
        content = "[A](A%20abc123def456789012.md) and [B](B%20def456abc789012345.md)"
        id_mapping = {
            "abc123def456789012": "uuid-a",
            "def456abc789012345": "uuid-b",
        }

        result = remap_links(content, id_mapping)

        self.assertIn("[A](/pages/uuid-a/)", result)
        self.assertIn("[B](/pages/uuid-b/)", result)

    def test_preserves_unmapped_links(self):
        """Preserves links without mapping."""
        content = "[Known](Known%20abc123def456789012.md) and [Unknown](Unknown%20xyz789abc012345678.md)"
        id_mapping = {"abc123def456789012": "uuid-known"}

        result = remap_links(content, id_mapping)

        self.assertIn("[Known](/pages/uuid-known/)", result)
        self.assertIn("[Unknown](Unknown%20xyz789abc012345678.md)", result)

    def test_preserves_surrounding_content(self):
        """Preserves content around links."""
        content = "Before [Link](Page%20abc123def456789012.md) after."
        id_mapping = {"abc123def456789012": "uuid-1"}

        result = remap_links(content, id_mapping)

        self.assertIn("Before", result)
        self.assertIn("after.", result)

    def test_remap_csv_link(self):
        """Remaps CSV database link to Hyperclast link."""
        content = "[Task Database](Database%20&%20Table/Task%20Database%20abc123def456789012.csv)"
        id_mapping = {"abc123def456789012": "uuid-db-1234"}

        result = remap_links(content, id_mapping)

        self.assertIn("[Task Database](/pages/uuid-db-1234/)", result)
        self.assertNotIn(".csv", result)

    def test_remap_mixed_md_and_csv_links(self):
        """Remaps both .md and .csv links correctly."""
        content = """[Page](Page%20abc123def456789012.md)
[Database](Database%20def456abc789012345.csv)"""
        id_mapping = {
            "abc123def456789012": "uuid-page",
            "def456abc789012345": "uuid-db",
        }

        result = remap_links(content, id_mapping)

        self.assertIn("[Page](/pages/uuid-page/)", result)
        self.assertIn("[Database](/pages/uuid-db/)", result)
        self.assertNotIn(".md", result)
        self.assertNotIn(".csv", result)


class TestFlattenPageTree(TestCase):
    """Tests for flatten_page_tree()."""

    def test_flatten_single_page(self):
        """Flattens single page correctly."""
        pages = [ParsedPage(title="Single", content="", original_path="single.md", source_hash="abc")]

        result = flatten_page_tree(pages)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].title, "Single")

    def test_flatten_nested_pages(self):
        """Flattens nested structure preserving all pages."""
        child = ParsedPage(title="Child", content="", original_path="parent/child.md", source_hash="def")
        parent = ParsedPage(title="Parent", content="", original_path="parent.md", source_hash="abc", children=[child])
        pages = [parent]

        result = flatten_page_tree(pages)

        self.assertEqual(len(result), 2)
        titles = [p.title for p in result]
        self.assertIn("Parent", titles)
        self.assertIn("Child", titles)

    def test_flatten_deep_nesting(self):
        """Flattens deeply nested structure."""
        grandchild = ParsedPage(title="Grandchild", content="", original_path="a/b/c.md", source_hash="ghi")
        child = ParsedPage(title="Child", content="", original_path="a/b.md", source_hash="def", children=[grandchild])
        parent = ParsedPage(title="Parent", content="", original_path="a.md", source_hash="abc", children=[child])

        result = flatten_page_tree([parent])

        self.assertEqual(len(result), 3)

    def test_flatten_multiple_top_level(self):
        """Flattens multiple top-level pages with children."""
        child1 = ParsedPage(title="Child1", content="", original_path="p1/c1.md", source_hash="c1")
        child2 = ParsedPage(title="Child2", content="", original_path="p2/c2.md", source_hash="c2")
        parent1 = ParsedPage(title="Parent1", content="", original_path="p1.md", source_hash="p1", children=[child1])
        parent2 = ParsedPage(title="Parent2", content="", original_path="p2.md", source_hash="p2", children=[child2])

        result = flatten_page_tree([parent1, parent2])

        self.assertEqual(len(result), 4)

    def test_flatten_empty_list(self):
        """Handles empty list."""
        result = flatten_page_tree([])
        self.assertEqual(result, [])


class TestTransformCalloutBlock(TestCase):
    """Tests for _transform_callout_block()."""

    def test_callout_single_line(self):
        """Transforms single-line callout."""
        lines = ["<aside>💡 This is a tip</aside>"]

        result, consumed = _transform_callout_block(lines, 0)

        self.assertEqual(consumed, 1)
        self.assertEqual(result, ["> 💡 This is a tip"])

    def test_callout_multiline(self):
        """Transforms multiline callout."""
        lines = [
            "<aside>",
            "⚠️ Warning message here.",
            "This is important.",
            "</aside>",
        ]

        result, consumed = _transform_callout_block(lines, 0)

        self.assertEqual(consumed, 4)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], "> ⚠️ Warning message here.")
        self.assertEqual(result[1], "> This is important.")

    def test_callout_with_emoji(self):
        """Preserves emoji in callout."""
        lines = ["<aside>📌 Important note with 🎉 emoji</aside>"]

        result, consumed = _transform_callout_block(lines, 0)

        self.assertEqual(result[0], "> 📌 Important note with 🎉 emoji")

    def test_callout_empty(self):
        """Handles empty callout."""
        lines = ["<aside></aside>"]

        result, consumed = _transform_callout_block(lines, 0)

        self.assertEqual(consumed, 1)
        self.assertEqual(result, [])


class TestTransformImagePaths(TestCase):
    """Tests for _transform_image_paths()."""

    def test_image_relative_path_decoded(self):
        """Decodes URL-encoded relative paths."""
        line = "![Screenshot](images/My%20Image%20abc123.png)"

        result = _transform_image_paths(line)

        self.assertEqual(result, "![Screenshot](images/My Image abc123.png)")

    def test_image_external_url_preserved(self):
        """Preserves external URLs without modification."""
        line = "![External](https://example.com/image.png?query=test%20space)"

        result = _transform_image_paths(line)

        self.assertEqual(result, "![External](https://example.com/image.png?query=test%20space)")

    def test_image_data_uri_preserved(self):
        """Preserves data URIs without modification."""
        line = "![Inline](data:image/png;base64,iVBORw0KGgo=)"

        result = _transform_image_paths(line)

        self.assertEqual(result, "![Inline](data:image/png;base64,iVBORw0KGgo=)")

    def test_multiple_images_in_line(self):
        """Handles multiple images in one line."""
        line = "![A](img%20a.png) and ![B](img%20b.png)"

        result = _transform_image_paths(line)

        self.assertEqual(result, "![A](img a.png) and ![B](img b.png)")

    def test_image_with_empty_alt(self):
        """Handles images with empty alt text."""
        line = "![](screenshot%20123.png)"

        result = _transform_image_paths(line)

        self.assertEqual(result, "![](screenshot 123.png)")


class TestTransformContentCallouts(TestCase):
    """Tests for callout handling in transform_content()."""

    def test_transform_callout_to_blockquote(self):
        """Transforms callout block in full content."""
        content = """Some text.

<aside>💡 This is a helpful tip.</aside>

More text after."""

        result = transform_content(content)

        self.assertIn("> 💡 This is a helpful tip.", result)
        self.assertNotIn("<aside>", result)
        self.assertIn("Some text.", result)
        self.assertIn("More text after.", result)

    def test_transform_multiple_callouts(self):
        """Handles multiple callouts in content."""
        content = """<aside>First callout</aside>

Paragraph.

<aside>Second callout</aside>"""

        result = transform_content(content)

        self.assertIn("> First callout", result)
        self.assertIn("> Second callout", result)
        self.assertIn("Paragraph.", result)


class TestTransformContentImages(TestCase):
    """Tests for image handling in transform_content()."""

    def test_transform_decodes_image_paths(self):
        """Decodes URL-encoded image paths."""
        content = "![My Image](My%20Screenshot%202024.png)"

        result = transform_content(content)

        self.assertIn("![My Image](My Screenshot 2024.png)", result)

    def test_transform_preserves_external_images(self):
        """Preserves external image URLs."""
        content = "![Logo](https://example.com/logo.png)"

        result = transform_content(content)

        self.assertIn("![Logo](https://example.com/logo.png)", result)


class TestTransformContentPreservation(TestCase):
    """Tests for content preservation in transform_content()."""

    def test_preserves_code_blocks(self):
        """Preserves fenced code blocks unchanged."""
        content = """Text before.

```python
def hello():
    print("Hello, World!")
```

Text after."""

        result = transform_content(content)

        self.assertIn("```python", result)
        self.assertIn('print("Hello, World!")', result)
        self.assertIn("```", result)

    def test_preserves_inline_code(self):
        """Preserves inline code unchanged."""
        content = "Use the `print()` function to output text."

        result = transform_content(content)

        self.assertIn("`print()`", result)

    def test_preserves_tables(self):
        """Preserves markdown tables."""
        content = """| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |"""

        result = transform_content(content)

        self.assertIn("| Header 1 | Header 2 |", result)
        self.assertIn("| Cell 1   | Cell 2   |", result)

    def test_preserves_equations(self):
        """Preserves LaTeX equations."""
        content = "The equation is $E = mc^2$ inline."

        result = transform_content(content)

        self.assertIn("$E = mc^2$", result)

    def test_preserves_block_equations(self):
        """Preserves block LaTeX equations."""
        content = """$$
\\int_0^\\infty e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}
$$"""

        result = transform_content(content)

        self.assertIn("$$", result)
        self.assertIn("\\int_0^\\infty", result)

    def test_preserves_todo_items(self):
        """Preserves checkbox/todo items."""
        content = """- [ ] Unchecked task
- [x] Completed task"""

        result = transform_content(content)

        self.assertIn("- [ ] Unchecked task", result)
        self.assertIn("- [x] Completed task", result)

    def test_preserves_blockquotes(self):
        """Preserves regular blockquotes."""
        content = """> This is a quote.
> Second line of quote."""

        result = transform_content(content)

        self.assertIn("> This is a quote.", result)
        self.assertIn("> Second line of quote.", result)


class TestIsSafePath(TestCase):
    """Tests for _is_safe_path()."""

    def test_safe_path_in_base(self):
        """Returns True for path within base directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            target = base / "subdir" / "file.txt"
            self.assertTrue(_is_safe_path(base, target))

    def test_safe_path_at_base(self):
        """Returns True for path at base directory level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            target = base / "file.txt"
            self.assertTrue(_is_safe_path(base, target))

    def test_unsafe_path_traversal(self):
        """Returns False for path traversal attempt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            target = base / ".." / "etc" / "passwd"
            self.assertFalse(_is_safe_path(base, target))

    def test_unsafe_path_outside_base(self):
        """Returns False for path completely outside base."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            target = Path("/etc/passwd")
            self.assertFalse(_is_safe_path(base, target))


class TestExtractZipSafely(TestCase):
    """Tests for extract_zip_safely()."""

    def _create_test_zip(self, files: dict, dest_path: Path) -> Path:
        """Helper to create a test zip file."""
        zip_path = dest_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, content in files.items():
                if isinstance(content, str):
                    content = content.encode("utf-8")
                zf.writestr(name, content)
        return zip_path

    def test_extracts_valid_zip(self):
        """Extracts valid zip file and returns statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            zip_path = self._create_test_zip({"test.txt": "hello world"}, tmppath)
            dest_dir = tmppath / "extracted"
            dest_dir.mkdir()

            result = extract_zip_safely(zip_path, dest_dir)

            self.assertEqual(result["files_extracted"], 1)
            self.assertEqual(result["bytes_extracted"], 11)
            self.assertIn("duration_seconds", result)
            self.assertTrue((dest_dir / "test.txt").exists())
            self.assertEqual((dest_dir / "test.txt").read_text(), "hello world")

    def test_extracts_multiple_files(self):
        """Extracts multiple files and tracks total size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            zip_path = self._create_test_zip(
                {
                    "file1.txt": "content 1",
                    "file2.txt": "content 2",
                    "subdir/file3.txt": "content 3",
                },
                tmppath,
            )
            dest_dir = tmppath / "extracted"
            dest_dir.mkdir()

            result = extract_zip_safely(zip_path, dest_dir)

            self.assertEqual(result["files_extracted"], 3)
            self.assertEqual(result["bytes_extracted"], 27)  # 9 + 9 + 9
            self.assertTrue((dest_dir / "subdir" / "file3.txt").exists())

    def test_rejects_path_traversal(self):
        """Rejects zip with path traversal attempt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            zip_path = tmppath / "malicious.zip"

            with zipfile.ZipFile(zip_path, "w") as zf:
                info = zipfile.ZipInfo("../../../etc/passwd")
                zf.writestr(info, "malicious")

            dest_dir = tmppath / "extracted"
            dest_dir.mkdir()

            with self.assertRaises(ImportInvalidZipError) as ctx:
                extract_zip_safely(zip_path, dest_dir)
            self.assertIn("Unsafe path", str(ctx.exception))

    def test_rejects_absolute_path(self):
        """Rejects zip with absolute path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            zip_path = tmppath / "malicious.zip"

            with zipfile.ZipFile(zip_path, "w") as zf:
                info = zipfile.ZipInfo("/etc/passwd")
                zf.writestr(info, "malicious")

            dest_dir = tmppath / "extracted"
            dest_dir.mkdir()

            with self.assertRaises(ImportInvalidZipError) as ctx:
                extract_zip_safely(zip_path, dest_dir)
            self.assertIn("Unsafe path", str(ctx.exception))

    @patch("imports.services.notion.settings")
    def test_rejects_exceeding_size_limit(self, mock_settings):
        """Rejects extraction that would exceed size limit."""
        mock_settings.WS_IMPORTS_MAX_UNCOMPRESSED_SIZE_BYTES = 50
        mock_settings.WS_IMPORTS_EXTRACTION_TIMEOUT_SECONDS = 300

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Create zip with content larger than limit
            zip_path = self._create_test_zip(
                {
                    "large1.txt": "x" * 30,
                    "large2.txt": "x" * 30,  # Total 60 bytes > 50 limit
                },
                tmppath,
            )
            dest_dir = tmppath / "extracted"
            dest_dir.mkdir()

            with self.assertRaises(ImportExtractedSizeExceededError):
                extract_zip_safely(zip_path, dest_dir)

    def test_rejects_exceeding_timeout(self):
        """Rejects extraction that exceeds timeout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            zip_path = self._create_test_zip({"test.txt": "content"}, tmppath)
            dest_dir = tmppath / "extracted"
            dest_dir.mkdir()

            # Use a very short timeout and patch time to simulate timeout
            with patch("imports.services.notion.time") as mock_time:
                # First call for start_time, second for elapsed check (simulates timeout)
                mock_time.time.side_effect = [0, 10]

                with self.assertRaises(ImportExtractionTimeoutError):
                    extract_zip_safely(zip_path, dest_dir, timeout_seconds=5)

    def test_handles_invalid_zip(self):
        """Raises ImportInvalidZipError for invalid zip file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            zip_path = tmppath / "invalid.zip"
            zip_path.write_bytes(b"not a valid zip file")

            dest_dir = tmppath / "extracted"
            dest_dir.mkdir()

            with self.assertRaises(ImportInvalidZipError):
                extract_zip_safely(zip_path, dest_dir)

    def test_skips_directories(self):
        """Directories are not counted in file count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            zip_path = tmppath / "test.zip"

            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("folder/", "")  # Directory entry
                zf.writestr("folder/file.txt", "content")

            dest_dir = tmppath / "extracted"
            dest_dir.mkdir()

            result = extract_zip_safely(zip_path, dest_dir)

            # Only the file should be counted
            self.assertEqual(result["files_extracted"], 1)


class TestExtractNestedZips(TestCase):
    """Tests for _extract_nested_zips()."""

    def _create_nested_zip(self, inner_files: dict, outer_name: str, dest_path: Path) -> Path:
        """Helper to create a zip containing another zip."""
        # Create inner zip in memory
        inner_buffer = io.BytesIO()
        with zipfile.ZipFile(inner_buffer, "w") as zf:
            for name, content in inner_files.items():
                if isinstance(content, str):
                    content = content.encode("utf-8")
                zf.writestr(name, content)
        inner_buffer.seek(0)

        # Write outer zip with inner zip inside
        outer_path = dest_path / outer_name
        outer_path.write_bytes(inner_buffer.getvalue())
        return outer_path

    def test_extracts_notion_nested_zip(self):
        """Extracts Notion ExportBlock nested zips."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create a Notion-pattern nested zip
            self._create_nested_zip(
                {"page.md": "# Test Page"},
                "ExportBlock-uuid123-Part-1.zip",
                tmppath,
            )

            _extract_nested_zips(tmppath)

            # Nested zip should be extracted and removed
            self.assertFalse((tmppath / "ExportBlock-uuid123-Part-1.zip").exists())
            self.assertTrue((tmppath / "page.md").exists())

    def test_extracts_multiple_notion_zips(self):
        """Extracts multiple Notion ExportBlock zips."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            self._create_nested_zip(
                {"page1.md": "# Page 1"},
                "ExportBlock-uuid-Part-1.zip",
                tmppath,
            )
            self._create_nested_zip(
                {"page2.md": "# Page 2"},
                "ExportBlock-uuid-Part-2.zip",
                tmppath,
            )

            _extract_nested_zips(tmppath)

            self.assertTrue((tmppath / "page1.md").exists())
            self.assertTrue((tmppath / "page2.md").exists())

    def test_rejects_non_notion_nested_zip(self):
        """Rejects nested zips that don't match Notion pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create a non-Notion nested zip
            self._create_nested_zip(
                {"malicious.txt": "evil content"},
                "random_archive.zip",
                tmppath,
            )

            with self.assertRaises(ImportNestedArchiveError) as ctx:
                _extract_nested_zips(tmppath)
            self.assertIn("forbidden nested archives", str(ctx.exception))
            self.assertIn("random_archive.zip", str(ctx.exception))

    def test_rejects_mixed_notion_and_arbitrary_zips(self):
        """Rejects if any nested zip doesn't match Notion pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create both Notion and non-Notion zips
            self._create_nested_zip(
                {"page.md": "# Page"},
                "ExportBlock-uuid-Part-1.zip",
                tmppath,
            )
            self._create_nested_zip(
                {"evil.txt": "malicious"},
                "arbitrary.zip",
                tmppath,
            )

            with self.assertRaises(ImportNestedArchiveError):
                _extract_nested_zips(tmppath)

    def test_enforces_depth_limit(self):
        """Enforces maximum nesting depth."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create a nested zip (at depth 1)
            self._create_nested_zip(
                {"page.md": "# Page"},
                "ExportBlock-uuid-Part-1.zip",
                tmppath,
            )

            # Depth 1 with max_depth=1 should work (extracts the zip)
            _extract_nested_zips(tmppath, current_depth=1, max_depth=1)

            # Create another nested zip for depth test
            self._create_nested_zip(
                {"page2.md": "# Page 2"},
                "ExportBlock-uuid-Part-2.zip",
                tmppath,
            )

            # Depth 2 with max_depth=1 should fail immediately
            with self.assertRaises(ImportNestedArchiveError) as ctx:
                _extract_nested_zips(tmppath, current_depth=2, max_depth=1)
            self.assertIn("depth 2 exceeds maximum 1", str(ctx.exception))

    def test_preserves_mixed_content_with_zips(self):
        """Does not extract zips when mixed with non-zip files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create a zip alongside a regular file
            self._create_nested_zip(
                {"inner.md": "# Inner"},
                "ExportBlock-uuid-Part-1.zip",
                tmppath,
            )
            (tmppath / "readme.md").write_text("# Readme")

            _extract_nested_zips(tmppath)

            # Zip should NOT be extracted (mixed content)
            self.assertTrue((tmppath / "ExportBlock-uuid-Part-1.zip").exists())
            self.assertFalse((tmppath / "inner.md").exists())

    def test_no_zips_does_nothing(self):
        """Does nothing when no zip files present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file.txt").write_text("content")

            # Should not raise
            _extract_nested_zips(tmppath)

            self.assertTrue((tmppath / "file.txt").exists())


class TestNotionNestedZipPattern(TestCase):
    """Tests for NOTION_NESTED_ZIP_PATTERN constant."""

    def test_matches_export_block_files(self):
        """Pattern matches Notion's ExportBlock files."""
        self.assertIn(NOTION_NESTED_ZIP_PATTERN, "ExportBlock-abc123-Part-1.zip")
        self.assertIn(NOTION_NESTED_ZIP_PATTERN, "ExportBlock-uuid-Part-2.zip")

    def test_does_not_match_arbitrary_files(self):
        """Pattern does not match arbitrary zip names."""
        self.assertNotIn(NOTION_NESTED_ZIP_PATTERN, "random.zip")
        self.assertNotIn(NOTION_NESTED_ZIP_PATTERN, "export.zip")
        self.assertNotIn(NOTION_NESTED_ZIP_PATTERN, "backup.zip")


class TestMalformedToggleBlocks(TestCase):
    """Tests for handling malformed HTML in toggle blocks."""

    def test_toggle_with_unclosed_details(self):
        """Handles toggle with missing closing tag gracefully."""
        lines = [
            "<details>",
            "<summary>Toggle Title</summary>",
            "Content line 1",
            "Content line 2",
            # No </details>
        ]

        result, consumed = _transform_toggle_block(lines, 0)

        # Should consume all remaining lines when no closing tag found
        self.assertEqual(consumed, len(lines))
        self.assertEqual(result[0], "- Toggle Title")

    def test_toggle_with_missing_summary(self):
        """Handles toggle without summary tag."""
        lines = [
            "<details>",
            "Just content, no summary",
            "</details>",
        ]

        result, consumed = _transform_toggle_block(lines, 0)

        # Should handle gracefully (may produce unexpected output, but shouldn't crash)
        self.assertEqual(consumed, 3)
        # The implementation may vary in how it handles this

    def test_toggle_with_nested_html(self):
        """Handles toggle with nested HTML elements."""
        lines = [
            "<details>",
            "<summary>Toggle with <strong>bold</strong></summary>",
            "<p>Paragraph content</p>",
            "</details>",
        ]

        result, consumed = _transform_toggle_block(lines, 0)

        self.assertEqual(consumed, 4)
        # Should contain the summary text
        self.assertTrue(any("Toggle with" in line for line in result))

    def test_toggle_with_empty_summary(self):
        """Handles toggle with empty summary tag."""
        lines = [
            "<details>",
            "<summary></summary>",
            "Content",
            "</details>",
        ]

        result, consumed = _transform_toggle_block(lines, 0)

        self.assertEqual(consumed, 4)


class TestMalformedCalloutBlocks(TestCase):
    """Tests for handling malformed HTML in callout blocks."""

    def test_callout_with_unclosed_aside(self):
        """Handles callout with missing closing tag gracefully."""
        lines = [
            "<aside>",
            "💡 Important note",
            "More content here",
            # No </aside>
        ]

        result, consumed = _transform_callout_block(lines, 0)

        # Should consume all remaining lines when no closing tag found
        self.assertEqual(consumed, len(lines))
        # Should still produce blockquote output
        self.assertTrue(all(line.startswith(">") or line == "" for line in result if line))

    def test_callout_with_nested_aside(self):
        """Handles callout with nested aside tags."""
        lines = [
            "<aside>",
            "Outer content",
            "<aside>Nested aside</aside>",
            "More outer content",
            "</aside>",
        ]

        result, consumed = _transform_callout_block(lines, 0)

        # Should handle nested tags gracefully
        self.assertGreater(consumed, 0)

    def test_callout_with_malformed_self_closing(self):
        """Handles malformed self-closing aside tag."""
        lines = ["<aside>Content<aside/>"]

        result, consumed = _transform_callout_block(lines, 0)

        # Should handle gracefully
        self.assertEqual(consumed, 1)

    def test_callout_with_only_whitespace(self):
        """Handles callout containing only whitespace."""
        lines = [
            "<aside>",
            "   ",
            "\t",
            "",
            "</aside>",
        ]

        result, consumed = _transform_callout_block(lines, 0)

        self.assertEqual(consumed, 5)
        # Should produce empty or minimal output
        self.assertTrue(len(result) <= 3)  # At most whitespace converted to blockquotes


class TestDeeplyNestedFolderStructures(TestCase):
    """Tests for handling deeply nested folder structures (30+ levels)."""

    def test_build_page_tree_with_30_level_nesting(self):
        """Can build page tree from 30+ level deep folder structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create a 30-level deep structure
            current_path = tmppath
            for i in range(30):
                page_name = f"Level{i} abc{i:016d}def{i:016d}"
                # Create the page file at current level
                (current_path / f"{page_name}.md").write_text(f"# Level {i}\n\nContent at level {i}")
                # Create child folder for next level
                current_path = current_path / page_name
                current_path.mkdir()

            # Create a leaf page at the deepest level
            (current_path / "DeepPage abc123def456789012345678901234.md").write_text("# Deep Page\n\nDeepest content")

            pages = build_page_tree(tmppath)

            # Should have 30 top-level pages (one per level)
            # Actually the tree should be nested, so only 1 top-level
            self.assertEqual(len(pages), 1)

            # Traverse to verify depth
            current = pages[0]
            depth = 0
            while current.children:
                depth += 1
                current = current.children[0]

            # Should reach at least 29 levels of nesting (30 total including root)
            self.assertGreaterEqual(depth, 29)

    def test_flatten_page_tree_with_deep_nesting(self):
        """Flattening deeply nested tree preserves all pages."""
        # Create a deep tree structure manually
        leaf = ParsedPage(
            title="Leaf",
            content="# Leaf",
            source_hash="leaf123456789012",
            children=[],
            original_path="leaf.md",
        )

        current = leaf
        for i in range(30):
            parent = ParsedPage(
                title=f"Level {i}",
                content=f"# Level {i}",
                source_hash=f"level{i:03d}456789012",
                children=[current],
                original_path=f"level{i}.md",
            )
            current = parent

        root = [current]
        flattened = flatten_page_tree(root)

        # Should have all 31 pages (30 levels + 1 leaf)
        self.assertEqual(len(flattened), 31)


class TestPagesWithOnlyImages(TestCase):
    """Tests for handling pages that contain only images (no text content)."""

    def test_parse_page_with_only_image(self):
        """Can parse a page that contains only an image."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create a page with only an image reference
            content = "![My Image](images/screenshot.png)"
            (tmppath / "Image Only Page abc123def456789012.md").write_text(content)

            pages = build_page_tree(tmppath)

            self.assertEqual(len(pages), 1)
            self.assertEqual(pages[0].title, "Image Only Page")
            self.assertIn("![My Image]", pages[0].content)

    def test_parse_page_with_multiple_images_no_text(self):
        """Can parse a page with multiple images but no text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            content = """![Image 1](img1.png)

![Image 2](img2.png)

![Image 3](img3.png)"""
            (tmppath / "Gallery abc123def456789012345678901234.md").write_text(content)

            pages = build_page_tree(tmppath)

            self.assertEqual(len(pages), 1)
            self.assertEqual(pages[0].title, "Gallery")
            self.assertIn("![Image 1]", pages[0].content)
            self.assertIn("![Image 2]", pages[0].content)
            self.assertIn("![Image 3]", pages[0].content)

    def test_parse_page_with_image_and_whitespace_only(self):
        """Can parse a page with image and only whitespace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            content = """


    ![Centered Image](centered.png)


"""
            (tmppath / "Whitespace Page abc123def456789012.md").write_text(content)

            pages = build_page_tree(tmppath)

            self.assertEqual(len(pages), 1)
            self.assertIn("![Centered Image]", pages[0].content)

    def test_transform_content_with_image_only(self):
        """Transform content handles image-only content correctly."""
        content = "![Screenshot](Screenshot%202024-01-15.png)"

        result = transform_content(content)

        # Should decode the URL encoding
        self.assertIn("Screenshot 2024-01-15.png", result)
        self.assertIn("![Screenshot]", result)

    def test_empty_page_after_title_removal(self):
        """Handles case where page becomes empty after title removal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create a page that's just the title (duplicate of filename)
            content = "# Empty Page Title"
            filepath = tmppath / "Empty Page Title abc123def456789012.md"
            filepath.write_text(content)

            parsed = parse_markdown_file(filepath, "Empty Page Title abc123def456789012.md")

            # Should parse successfully even if content is empty after title removal
            self.assertIsNotNone(parsed)
            self.assertEqual(parsed.title, "Empty Page Title")


class TestVeryLongPageTitles(TestCase):
    """Tests for handling very long page titles (>100 chars)."""

    def test_parse_filename_with_100_char_title(self):
        """Can parse filename with 100+ character title."""
        long_title = "A" * 100
        filename = f"{long_title} abc123def456789012.md"

        title, hash_val = parse_notion_filename(filename)

        self.assertEqual(title, long_title)
        self.assertEqual(hash_val, "abc123def456789012")

    def test_parse_filename_with_200_char_title(self):
        """Can parse filename with 200 character title."""
        long_title = "Very Long Title " * 12 + "End"  # ~200 chars
        filename = f"{long_title} abc123def456789012345678901234.md"

        title, hash_val = parse_notion_filename(filename)

        self.assertEqual(title, long_title)
        self.assertEqual(hash_val, "abc123def456789012345678901234")

    def test_build_tree_with_long_titles(self):
        """Can build page tree with very long page titles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            long_title = (
                "This is a very long page title that exceeds one hundred characters in length for testing purposes here"
            )
            self.assertGreater(len(long_title), 100)

            filename = f"{long_title} abc123def456789012345678901234.md"
            (tmppath / filename).write_text(f"# {long_title}\n\nContent here.")

            pages = build_page_tree(tmppath)

            self.assertEqual(len(pages), 1)
            self.assertEqual(pages[0].title, long_title)

    def test_long_title_with_special_characters(self):
        """Can handle long titles with special characters."""
        # Create a long title with various special chars
        long_title = (
            "Project Planning - Q1 2024: Goals, Objectives & Key Results (OKRs) for the Engineering Team's Success!!!"
        )
        self.assertGreater(len(long_title), 100)

        filename = f"{long_title} abc123def456789012.md"
        title, hash_val = parse_notion_filename(filename)

        self.assertEqual(title, long_title)
        self.assertEqual(hash_val, "abc123def456789012")

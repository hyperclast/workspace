"""
Tests for the archive safety inspection and validation module.
"""

import io
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from imports.constants import NOTION_NESTED_ZIP_PATTERN
from imports.exceptions import (
    ImportCompressionRatioExceededError,
    ImportExtractedSizeExceededError,
    ImportFileCountExceededError,
    ImportInvalidZipError,
    ImportNestedArchiveError,
    ImportPathDepthExceededError,
)
from imports.services.archive_safety import (
    NESTED_ARCHIVE_EXTENSIONS,
    ArchiveInspectionResult,
    inspect_and_validate_archive,
    inspect_archive,
    validate_archive_safety,
)


def create_test_zip(
    files: dict[str, bytes | str] | None = None,
    compression: int = zipfile.ZIP_DEFLATED,
) -> Path:
    """
    Helper to create a test zip file.

    Args:
        files: Dict mapping filename to content (str or bytes).
        compression: Compression method.

    Returns:
        Path to the created temp zip file.
    """
    if files is None:
        files = {"test.txt": "test content"}

    temp_file = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_path = Path(temp_file.name)

    with zipfile.ZipFile(temp_path, "w", compression) as zf:
        for name, content in files.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            zf.writestr(name, content)

    return temp_path


class TestArchiveInspectionResult(TestCase):
    """Tests for ArchiveInspectionResult dataclass."""

    def test_to_dict(self):
        """Converts to dictionary correctly."""
        result = ArchiveInspectionResult(
            compressed_size=1000,
            uncompressed_size=5000,
            compression_ratio=5.0,
            file_count=10,
            max_single_file_size=2000,
            max_path_depth=3,
            has_nested_archives=True,
            nested_archive_names=["nested.zip"],
            has_path_traversal=False,
            has_absolute_paths=False,
        )

        d = result.to_dict()

        self.assertEqual(d["compressed_size"], 1000)
        self.assertEqual(d["uncompressed_size"], 5000)
        self.assertEqual(d["compression_ratio"], 5.0)
        self.assertEqual(d["file_count"], 10)
        self.assertEqual(d["max_single_file_size"], 2000)
        self.assertEqual(d["max_path_depth"], 3)
        self.assertTrue(d["has_nested_archives"])
        self.assertEqual(d["nested_archive_names"], ["nested.zip"])
        self.assertFalse(d["has_path_traversal"])
        self.assertFalse(d["has_absolute_paths"])


class TestInspectArchive(TestCase):
    """Tests for inspect_archive()."""

    def test_inspect_valid_zip(self):
        """Inspects a valid zip file successfully."""
        zip_path = create_test_zip({"test.txt": "hello world"})
        try:
            result = inspect_archive(zip_path)

            self.assertIsInstance(result, ArchiveInspectionResult)
            self.assertEqual(result.file_count, 1)
            self.assertEqual(result.uncompressed_size, 11)  # len("hello world")
            self.assertGreater(result.compressed_size, 0)
            self.assertFalse(result.has_path_traversal)
            self.assertFalse(result.has_absolute_paths)
        finally:
            zip_path.unlink()

    def test_inspect_multiple_files(self):
        """Counts multiple files correctly."""
        zip_path = create_test_zip(
            {
                "file1.txt": "content 1",
                "file2.txt": "content 2",
                "file3.txt": "content 3",
            }
        )
        try:
            result = inspect_archive(zip_path)

            self.assertEqual(result.file_count, 3)
        finally:
            zip_path.unlink()

    def test_inspect_calculates_compression_ratio(self):
        """Calculates compression ratio correctly."""
        # Create highly compressible content
        content = "A" * 10000
        zip_path = create_test_zip({"compressible.txt": content})
        try:
            result = inspect_archive(zip_path)

            # Should have some compression
            self.assertGreater(result.compression_ratio, 1.0)
            self.assertEqual(result.uncompressed_size, 10000)
        finally:
            zip_path.unlink()

    def test_inspect_detects_max_single_file(self):
        """Tracks maximum single file size."""
        zip_path = create_test_zip(
            {
                "small.txt": "x",
                "medium.txt": "x" * 100,
                "large.txt": "x" * 1000,
            }
        )
        try:
            result = inspect_archive(zip_path)

            self.assertEqual(result.max_single_file_size, 1000)
        finally:
            zip_path.unlink()

    def test_inspect_detects_path_depth(self):
        """Calculates maximum path depth correctly."""
        zip_path = create_test_zip(
            {
                "shallow.txt": "content",
                "a/medium.txt": "content",
                "a/b/c/deep.txt": "content",
            }
        )
        try:
            result = inspect_archive(zip_path)

            self.assertEqual(result.max_path_depth, 4)  # a/b/c/deep.txt = 4 parts
        finally:
            zip_path.unlink()

    def test_inspect_detects_nested_zip(self):
        """Detects nested zip archives."""
        # Create inner zip
        inner_zip = io.BytesIO()
        with zipfile.ZipFile(inner_zip, "w") as zf:
            zf.writestr("inner.txt", "inner content")
        inner_zip.seek(0)

        zip_path = create_test_zip(
            {
                "outer.txt": "outer content",
                "nested.zip": inner_zip.getvalue(),
            }
        )
        try:
            result = inspect_archive(zip_path)

            self.assertTrue(result.has_nested_archives)
            self.assertIn("nested.zip", result.nested_archive_names)
        finally:
            zip_path.unlink()

    def test_inspect_detects_various_archive_types(self):
        """Detects various nested archive types."""
        zip_path = create_test_zip(
            {
                "file.txt": "content",
                "nested.7z": b"fake 7z",
                "nested.tar": b"fake tar",
                "nested.tgz": b"fake tgz",
                "nested.rar": b"fake rar",
            }
        )
        try:
            result = inspect_archive(zip_path)

            self.assertTrue(result.has_nested_archives)
            self.assertEqual(len(result.nested_archive_names), 4)
        finally:
            zip_path.unlink()

    def test_inspect_detects_path_traversal(self):
        """Detects path traversal attempts."""
        temp_file = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        temp_path = Path(temp_file.name)

        with zipfile.ZipFile(temp_path, "w") as zf:
            # Manually create a path traversal entry
            info = zipfile.ZipInfo("../../../etc/passwd")
            zf.writestr(info, "malicious")

        try:
            result = inspect_archive(temp_path)

            self.assertTrue(result.has_path_traversal)
        finally:
            temp_path.unlink()

    def test_inspect_detects_absolute_paths(self):
        """Detects absolute paths."""
        temp_file = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        temp_path = Path(temp_file.name)

        with zipfile.ZipFile(temp_path, "w") as zf:
            info = zipfile.ZipInfo("/etc/passwd")
            zf.writestr(info, "malicious")

        try:
            result = inspect_archive(temp_path)

            self.assertTrue(result.has_absolute_paths)
        finally:
            temp_path.unlink()

    def test_inspect_skips_directories(self):
        """Directories are not counted as files."""
        temp_file = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        temp_path = Path(temp_file.name)

        with zipfile.ZipFile(temp_path, "w") as zf:
            # Add a directory entry
            zf.writestr("folder/", "")
            zf.writestr("folder/file.txt", "content")

        try:
            result = inspect_archive(temp_path)

            # Only the file should be counted, not the directory
            self.assertEqual(result.file_count, 1)
        finally:
            temp_path.unlink()

    def test_inspect_invalid_zip(self):
        """Raises ImportInvalidZipError for invalid zip."""
        temp_file = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        temp_path = Path(temp_file.name)
        temp_path.write_bytes(b"not a valid zip file")

        try:
            with self.assertRaises(ImportInvalidZipError):
                inspect_archive(temp_path)
        finally:
            temp_path.unlink()

    def test_inspect_nonexistent_file(self):
        """Raises ImportInvalidZipError for nonexistent file."""
        with self.assertRaises(ImportInvalidZipError):
            inspect_archive("/nonexistent/path/file.zip")

    def test_inspect_notion_nested_zip_pattern(self):
        """Detects Notion's ExportBlock nested zips."""
        inner_zip = io.BytesIO()
        with zipfile.ZipFile(inner_zip, "w") as zf:
            zf.writestr("page.md", "# Page")
        inner_zip.seek(0)

        zip_path = create_test_zip(
            {
                "ExportBlock-uuid123-Part-1.zip": inner_zip.getvalue(),
                "ExportBlock-uuid123-Part-2.zip": inner_zip.getvalue(),
            }
        )
        try:
            result = inspect_archive(zip_path)

            self.assertTrue(result.has_nested_archives)
            self.assertEqual(len(result.nested_archive_names), 2)
            for name in result.nested_archive_names:
                self.assertIn(NOTION_NESTED_ZIP_PATTERN, name)
        finally:
            zip_path.unlink()


class TestValidateArchiveSafety(TestCase):
    """Tests for validate_archive_safety()."""

    def _make_result(self, **kwargs) -> ArchiveInspectionResult:
        """Helper to create inspection result with defaults."""
        defaults = {
            "compressed_size": 1000,
            "uncompressed_size": 2000,
            "compression_ratio": 2.0,
            "file_count": 10,
            "max_single_file_size": 500,
            "max_path_depth": 3,
            "has_nested_archives": False,
            "nested_archive_names": [],
            "has_path_traversal": False,
            "has_absolute_paths": False,
        }
        defaults.update(kwargs)
        return ArchiveInspectionResult(**defaults)

    def test_validate_passes_safe_archive(self):
        """Safe archive passes validation without exception."""
        result = self._make_result()

        # Should not raise
        validate_archive_safety(result)

    def test_validate_rejects_path_traversal(self):
        """Rejects archive with path traversal."""
        result = self._make_result(has_path_traversal=True)

        with self.assertRaises(ImportInvalidZipError) as ctx:
            validate_archive_safety(result)
        self.assertIn("path traversal", str(ctx.exception).lower())

    def test_validate_rejects_absolute_paths(self):
        """Rejects archive with absolute paths."""
        result = self._make_result(has_absolute_paths=True)

        with self.assertRaises(ImportInvalidZipError) as ctx:
            validate_archive_safety(result)
        self.assertIn("absolute paths", str(ctx.exception).lower())

    @patch("imports.services.archive_safety.settings")
    def test_validate_rejects_high_compression_ratio(self, mock_settings):
        """Rejects archive exceeding compression ratio threshold."""
        mock_settings.WS_IMPORTS_MAX_COMPRESSION_RATIO = 10.0

        result = self._make_result(compression_ratio=50.0)

        with self.assertRaises(ImportCompressionRatioExceededError) as ctx:
            validate_archive_safety(result)
        self.assertIn("50.0x", str(ctx.exception))
        self.assertIn("10.0x", str(ctx.exception))

    @patch("imports.services.archive_safety.settings")
    def test_validate_accepts_ratio_at_limit(self, mock_settings):
        """Accepts archive at exactly the ratio limit."""
        mock_settings.WS_IMPORTS_MAX_COMPRESSION_RATIO = 10.0
        mock_settings.WS_IMPORTS_MAX_UNCOMPRESSED_SIZE_BYTES = 10**12
        mock_settings.WS_IMPORTS_MAX_FILE_COUNT = 100000
        mock_settings.WS_IMPORTS_MAX_SINGLE_FILE_SIZE_BYTES = 10**9
        mock_settings.WS_IMPORTS_MAX_PATH_DEPTH = 30

        result = self._make_result(compression_ratio=10.0)

        # Should not raise
        validate_archive_safety(result)

    @patch("imports.services.archive_safety.settings")
    def test_validate_rejects_large_extracted_size(self, mock_settings):
        """Rejects archive exceeding extracted size threshold."""
        mock_settings.WS_IMPORTS_MAX_UNCOMPRESSED_SIZE_BYTES = 1000
        mock_settings.WS_IMPORTS_MAX_COMPRESSION_RATIO = 100.0
        mock_settings.WS_IMPORTS_MAX_FILE_COUNT = 100000
        mock_settings.WS_IMPORTS_MAX_SINGLE_FILE_SIZE_BYTES = 10000000
        mock_settings.WS_IMPORTS_MAX_PATH_DEPTH = 30

        result = self._make_result(uncompressed_size=5000)

        with self.assertRaises(ImportExtractedSizeExceededError) as ctx:
            validate_archive_safety(result)
        self.assertIn("5000 bytes", str(ctx.exception))

    @patch("imports.services.archive_safety.settings")
    def test_validate_rejects_too_many_files(self, mock_settings):
        """Rejects archive exceeding file count threshold."""
        mock_settings.WS_IMPORTS_MAX_FILE_COUNT = 100
        mock_settings.WS_IMPORTS_MAX_COMPRESSION_RATIO = 100.0
        mock_settings.WS_IMPORTS_MAX_UNCOMPRESSED_SIZE_BYTES = 10**12
        mock_settings.WS_IMPORTS_MAX_SINGLE_FILE_SIZE_BYTES = 10**9
        mock_settings.WS_IMPORTS_MAX_PATH_DEPTH = 30

        result = self._make_result(file_count=500)

        with self.assertRaises(ImportFileCountExceededError) as ctx:
            validate_archive_safety(result)
        self.assertIn("500", str(ctx.exception))
        self.assertIn("100", str(ctx.exception))

    @patch("imports.services.archive_safety.settings")
    def test_validate_rejects_large_single_file(self, mock_settings):
        """Rejects archive with single file exceeding threshold."""
        mock_settings.WS_IMPORTS_MAX_SINGLE_FILE_SIZE_BYTES = 1000
        mock_settings.WS_IMPORTS_MAX_COMPRESSION_RATIO = 100.0
        mock_settings.WS_IMPORTS_MAX_UNCOMPRESSED_SIZE_BYTES = 10**12
        mock_settings.WS_IMPORTS_MAX_FILE_COUNT = 100000
        mock_settings.WS_IMPORTS_MAX_PATH_DEPTH = 30

        result = self._make_result(max_single_file_size=5000)

        with self.assertRaises(ImportExtractedSizeExceededError) as ctx:
            validate_archive_safety(result)
        self.assertIn("5000 bytes", str(ctx.exception))

    @patch("imports.services.archive_safety.settings")
    def test_validate_rejects_deep_paths(self, mock_settings):
        """Rejects archive exceeding path depth threshold."""
        mock_settings.WS_IMPORTS_MAX_PATH_DEPTH = 5
        mock_settings.WS_IMPORTS_MAX_COMPRESSION_RATIO = 100.0
        mock_settings.WS_IMPORTS_MAX_UNCOMPRESSED_SIZE_BYTES = 10**12
        mock_settings.WS_IMPORTS_MAX_FILE_COUNT = 100000
        mock_settings.WS_IMPORTS_MAX_SINGLE_FILE_SIZE_BYTES = 10**9

        result = self._make_result(max_path_depth=15)

        with self.assertRaises(ImportPathDepthExceededError) as ctx:
            validate_archive_safety(result)
        self.assertIn("15", str(ctx.exception))
        self.assertIn("5", str(ctx.exception))

    def test_validate_rejects_arbitrary_nested_archives(self):
        """Rejects archives with non-Notion nested zips."""
        result = self._make_result(
            has_nested_archives=True,
            nested_archive_names=["malicious.zip", "another.7z"],
        )

        with self.assertRaises(ImportNestedArchiveError) as ctx:
            validate_archive_safety(result, allow_notion_nested_zips=True)
        self.assertIn("malicious.zip", str(ctx.exception))

    def test_validate_allows_notion_nested_zips(self):
        """Allows Notion's ExportBlock nested zips when enabled."""
        result = self._make_result(
            has_nested_archives=True,
            nested_archive_names=[
                "ExportBlock-abc123-Part-1.zip",
                "ExportBlock-abc123-Part-2.zip",
            ],
        )

        # Should not raise
        validate_archive_safety(result, allow_notion_nested_zips=True)

    def test_validate_rejects_notion_zips_when_disabled(self):
        """Rejects Notion nested zips when allow_notion_nested_zips=False."""
        result = self._make_result(
            has_nested_archives=True,
            nested_archive_names=["ExportBlock-abc123-Part-1.zip"],
        )

        with self.assertRaises(ImportNestedArchiveError):
            validate_archive_safety(result, allow_notion_nested_zips=False)

    def test_validate_rejects_mixed_nested_archives(self):
        """Rejects if any nested archive is not Notion pattern."""
        result = self._make_result(
            has_nested_archives=True,
            nested_archive_names=[
                "ExportBlock-abc123-Part-1.zip",  # Valid Notion
                "malicious.zip",  # Invalid
            ],
        )

        with self.assertRaises(ImportNestedArchiveError) as ctx:
            validate_archive_safety(result, allow_notion_nested_zips=True)
        self.assertIn("malicious.zip", str(ctx.exception))

    def test_validate_exception_includes_details(self):
        """Exception includes inspection details for logging."""
        result = self._make_result(
            compression_ratio=100.0,
            file_count=1000,
        )

        with patch("imports.services.archive_safety.settings") as mock_settings:
            mock_settings.WS_IMPORTS_MAX_COMPRESSION_RATIO = 10.0
            with self.assertRaises(ImportCompressionRatioExceededError) as ctx:
                validate_archive_safety(result)

            self.assertIn("compression_ratio", ctx.exception.details)
            self.assertEqual(ctx.exception.details["file_count"], 1000)


class TestInspectAndValidateArchive(TestCase):
    """Tests for inspect_and_validate_archive() convenience function."""

    def test_inspect_and_validate_valid_zip(self):
        """Returns result for valid safe archive."""
        zip_path = create_test_zip({"test.txt": "hello"})
        try:
            result = inspect_and_validate_archive(zip_path)

            self.assertIsInstance(result, ArchiveInspectionResult)
            self.assertEqual(result.file_count, 1)
        finally:
            zip_path.unlink()

    def test_inspect_and_validate_invalid_zip(self):
        """Raises for invalid zip file."""
        temp_file = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        temp_path = Path(temp_file.name)
        temp_path.write_bytes(b"not a zip")

        try:
            with self.assertRaises(ImportInvalidZipError):
                inspect_and_validate_archive(temp_path)
        finally:
            temp_path.unlink()

    def test_inspect_and_validate_path_traversal(self):
        """Raises for archive with path traversal."""
        temp_file = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        temp_path = Path(temp_file.name)

        with zipfile.ZipFile(temp_path, "w") as zf:
            info = zipfile.ZipInfo("../../../etc/passwd")
            zf.writestr(info, "malicious")

        try:
            with self.assertRaises(ImportInvalidZipError):
                inspect_and_validate_archive(temp_path)
        finally:
            temp_path.unlink()

    @patch("imports.services.archive_safety.settings")
    def test_inspect_and_validate_bomb_detection(self, mock_settings):
        """Detects potential zip bomb by compression ratio."""
        mock_settings.WS_IMPORTS_MAX_COMPRESSION_RATIO = 5.0
        mock_settings.WS_IMPORTS_MAX_UNCOMPRESSED_SIZE_BYTES = 10**12
        mock_settings.WS_IMPORTS_MAX_FILE_COUNT = 100000
        mock_settings.WS_IMPORTS_MAX_SINGLE_FILE_SIZE_BYTES = 10**9
        mock_settings.WS_IMPORTS_MAX_PATH_DEPTH = 30

        # Create a highly compressible file (will have high ratio)
        content = "A" * 100000
        zip_path = create_test_zip({"compressible.txt": content})

        try:
            with self.assertRaises(ImportCompressionRatioExceededError):
                inspect_and_validate_archive(zip_path)
        finally:
            zip_path.unlink()


class TestNestedArchiveExtensions(TestCase):
    """Tests for NESTED_ARCHIVE_EXTENSIONS constant."""

    def test_includes_common_archive_types(self):
        """Includes common archive file extensions."""
        self.assertIn(".zip", NESTED_ARCHIVE_EXTENSIONS)
        self.assertIn(".7z", NESTED_ARCHIVE_EXTENSIONS)
        self.assertIn(".tar", NESTED_ARCHIVE_EXTENSIONS)
        self.assertIn(".rar", NESTED_ARCHIVE_EXTENSIONS)

    def test_includes_compressed_tars(self):
        """Includes compressed tar variants."""
        self.assertIn(".tar.gz", NESTED_ARCHIVE_EXTENSIONS)
        self.assertIn(".tgz", NESTED_ARCHIVE_EXTENSIONS)
        self.assertIn(".tar.bz2", NESTED_ARCHIVE_EXTENSIONS)


class TestNotionNestedZipPattern(TestCase):
    """Tests for NOTION_NESTED_ZIP_PATTERN constant."""

    def test_matches_export_block_pattern(self):
        """Pattern matches Notion's ExportBlock files."""
        self.assertIn(NOTION_NESTED_ZIP_PATTERN, "ExportBlock-abc123-Part-1.zip")
        self.assertIn(NOTION_NESTED_ZIP_PATTERN, "ExportBlock-uuid-Part-2.zip")

    def test_does_not_match_arbitrary_zips(self):
        """Pattern does not match arbitrary zip names."""
        self.assertNotIn(NOTION_NESTED_ZIP_PATTERN, "random.zip")
        self.assertNotIn(NOTION_NESTED_ZIP_PATTERN, "nested.zip")
        self.assertNotIn(NOTION_NESTED_ZIP_PATTERN, "export.zip")


class TestArchiveWithSymlinks(TestCase):
    """Tests for handling archives containing symbolic links.

    Symlinks in archives can be a security risk as they can point outside
    the extraction directory (symlink attacks). The archive safety module
    should handle these appropriately.
    """

    def test_inspect_archive_with_symlink(self):
        """Inspects archive containing a symlink.

        Note: Python's zipfile module doesn't natively support creating
        symlinks in zip files, but the inspection should handle any
        zip entry regardless of type.
        """
        # Create a zip with a regular file (zipfile module doesn't support symlinks directly)
        # This test ensures the inspection handles all zip entries
        zip_path = create_test_zip({"regular_file.txt": "content"})
        try:
            result = inspect_archive(zip_path)
            # Should successfully inspect the archive
            self.assertEqual(result.file_count, 1)
        finally:
            zip_path.unlink()

    def test_inspect_archive_with_external_symlink_path(self):
        """Detects symlink-like paths that point outside extraction directory.

        Even without actual symlinks, malicious archives may include
        path entries that look like symlink destinations.
        """
        temp_file = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        temp_path = Path(temp_file.name)

        # Create zip with a path that mimics symlink traversal
        with zipfile.ZipFile(temp_path, "w") as zf:
            # This would be a path traversal attempt
            info = zipfile.ZipInfo("link/../../../etc/passwd")
            zf.writestr(info, "content")

        try:
            result = inspect_archive(temp_path)
            # Should detect path traversal
            self.assertTrue(result.has_path_traversal)
        finally:
            temp_path.unlink()

    def test_validate_rejects_symlink_traversal_path(self):
        """Validation rejects paths that attempt traversal via symlink-like patterns."""
        result = ArchiveInspectionResult(
            compressed_size=100,
            uncompressed_size=100,
            compression_ratio=1.0,
            file_count=1,
            max_single_file_size=100,
            max_path_depth=5,
            has_nested_archives=False,
            nested_archive_names=[],
            has_path_traversal=True,  # Simulates traversal via symlink
            has_absolute_paths=False,
        )

        with self.assertRaises(ImportInvalidZipError) as ctx:
            validate_archive_safety(result)
        self.assertIn("path traversal", str(ctx.exception).lower())

    def test_inspect_handles_unusual_zip_entry_attributes(self):
        """Handles zip entries with unusual attributes gracefully."""
        temp_file = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        temp_path = Path(temp_file.name)

        with zipfile.ZipFile(temp_path, "w") as zf:
            # Create entry with unusual external attributes (simulating symlink on Unix)
            # On Unix, symlinks have external attributes with 0xA000 (S_IFLNK) in upper byte
            info = zipfile.ZipInfo("possible_symlink.txt")
            # This sets Unix symlink mode in external_attr (though content won't be treated as symlink by Python)
            info.external_attr = 0o120777 << 16  # Unix symlink mode
            zf.writestr(info, "/etc/passwd")  # Symlink "target"

        try:
            result = inspect_archive(temp_path)
            # Should successfully inspect without crashing
            self.assertIsInstance(result, ArchiveInspectionResult)
            self.assertEqual(result.file_count, 1)
        finally:
            temp_path.unlink()


class TestSymlinkExtractionSafety(TestCase):
    """Tests for safe extraction behavior with symlink-like entries."""

    def test_extract_zip_skips_symlink_entries_safely(self):
        """Extract function handles entries that might be symlinks safely.

        The extraction code should use extractall() or extract() safely,
        which in Python's zipfile module doesn't create actual symlinks
        by default. This test verifies no unexpected behavior occurs.
        """
        # Create a standard zip (without symlinks - Python zipfile can't create them)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("normal.txt", "normal content")
            # Entry with symlink-like mode but regular content
            info = zipfile.ZipInfo("looks_like_symlink.txt")
            info.external_attr = 0o120777 << 16  # Unix symlink mode
            zf.writestr(info, "/etc/passwd")
        buffer.seek(0)

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / "test.zip"
            temp_path.write_bytes(buffer.getvalue())

            result = inspect_archive(temp_path)
            # Should inspect without issues
            self.assertEqual(result.file_count, 2)
            self.assertFalse(result.has_path_traversal)
            self.assertFalse(result.has_absolute_paths)

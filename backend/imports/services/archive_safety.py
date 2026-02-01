"""
Archive safety inspection and validation.

This module provides pre-extraction inspection of ZIP archives to detect
potential zip bombs and other malicious archive patterns. Inspection uses
only the archive's directory listing (metadata), NOT the actual file contents,
making it safe to run before extraction.
"""

import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from imports.constants import NOTION_NESTED_ZIP_PATTERN
from imports.exceptions import (
    ImportCompressionRatioExceededError,
    ImportExtractedSizeExceededError,
    ImportFileCountExceededError,
    ImportInvalidZipError,
    ImportNestedArchiveError,
    ImportPathDepthExceededError,
)

logger = logging.getLogger(__name__)


@dataclass
class ArchiveInspectionResult:
    """Results from pre-extraction archive inspection."""

    compressed_size: int
    uncompressed_size: int
    compression_ratio: float
    file_count: int
    max_single_file_size: int
    max_path_depth: int
    has_nested_archives: bool
    nested_archive_names: list[str]
    has_path_traversal: bool
    has_absolute_paths: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/storage."""
        return {
            "compressed_size": self.compressed_size,
            "uncompressed_size": self.uncompressed_size,
            "compression_ratio": self.compression_ratio,
            "file_count": self.file_count,
            "max_single_file_size": self.max_single_file_size,
            "max_path_depth": self.max_path_depth,
            "has_nested_archives": self.has_nested_archives,
            "nested_archive_names": self.nested_archive_names,
            "has_path_traversal": self.has_path_traversal,
            "has_absolute_paths": self.has_absolute_paths,
        }


# Archive file extensions that could contain nested archives
NESTED_ARCHIVE_EXTENSIONS = {".zip", ".7z", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".rar"}


def inspect_archive(file_path: str | Path) -> ArchiveInspectionResult:
    """
    Inspect archive metadata WITHOUT extracting contents.

    Uses zipfile's directory listing to compute metrics about the archive
    without actually decompressing any data.

    Args:
        file_path: Path to the zip file to inspect.

    Returns:
        ArchiveInspectionResult with computed metrics.

    Raises:
        ImportInvalidZipError: If the file is not a valid zip archive.
    """
    file_path = Path(file_path)

    try:
        compressed_size = file_path.stat().st_size
    except OSError as e:
        raise ImportInvalidZipError(f"Cannot read file: {e}")

    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            return _inspect_zipfile(zf, compressed_size)
    except zipfile.BadZipFile as e:
        raise ImportInvalidZipError(f"Invalid zip file: {e}")


def _inspect_zipfile(zf: zipfile.ZipFile, compressed_size: int) -> ArchiveInspectionResult:
    """
    Inspect an already-opened zipfile.

    Args:
        zf: Open zipfile object.
        compressed_size: Size of the compressed archive on disk.

    Returns:
        ArchiveInspectionResult with computed metrics.
    """
    total_uncompressed = 0
    max_single_file = 0
    max_depth = 0
    file_count = 0
    nested_archives = []
    has_traversal = False
    has_absolute = False

    for info in zf.infolist():
        # Skip directories (they have no content)
        if info.is_dir():
            continue

        file_count += 1
        total_uncompressed += info.file_size
        max_single_file = max(max_single_file, info.file_size)

        # Path analysis
        path = Path(info.filename)
        depth = len(path.parts)
        max_depth = max(max_depth, depth)

        # Security checks
        if ".." in path.parts:
            has_traversal = True
        if path.is_absolute():
            has_absolute = True

        # Nested archive detection
        suffix_lower = path.suffix.lower()
        if suffix_lower in NESTED_ARCHIVE_EXTENSIONS:
            nested_archives.append(info.filename)

    # Calculate compression ratio (avoid division by zero)
    ratio = total_uncompressed / compressed_size if compressed_size > 0 else 0.0

    return ArchiveInspectionResult(
        compressed_size=compressed_size,
        uncompressed_size=total_uncompressed,
        compression_ratio=ratio,
        file_count=file_count,
        max_single_file_size=max_single_file,
        max_path_depth=max_depth,
        has_nested_archives=len(nested_archives) > 0,
        nested_archive_names=nested_archives,
        has_path_traversal=has_traversal,
        has_absolute_paths=has_absolute,
    )


def validate_archive_safety(
    result: ArchiveInspectionResult,
    allow_notion_nested_zips: bool = True,
) -> None:
    """
    Validate archive inspection results against safety thresholds.

    Raises appropriate exception if any threshold is exceeded.

    Args:
        result: Inspection results from inspect_archive().
        allow_notion_nested_zips: If True, allows ExportBlock-*.zip patterns
            (which are legitimate Notion export artifacts).

    Raises:
        ImportInvalidZipError: For path traversal or absolute paths.
        ImportCompressionRatioExceededError: When ratio exceeds threshold.
        ImportExtractedSizeExceededError: When size exceeds threshold.
        ImportFileCountExceededError: When file count exceeds threshold.
        ImportNestedArchiveError: When forbidden nested archives found.
        ImportPathDepthExceededError: When path depth exceeds threshold.
    """
    # Path traversal (always reject - this is a security issue)
    if result.has_path_traversal:
        raise ImportInvalidZipError("Archive contains path traversal sequences (..)")

    if result.has_absolute_paths:
        raise ImportInvalidZipError("Archive contains absolute paths")

    # Compression ratio
    max_ratio = getattr(settings, "WS_IMPORTS_MAX_COMPRESSION_RATIO", 30.0)
    if result.compression_ratio > max_ratio:
        raise ImportCompressionRatioExceededError(
            f"Compression ratio {result.compression_ratio:.1f}x exceeds limit of {max_ratio}x",
            details=result.to_dict(),
        )

    # Total extracted size
    max_size = getattr(settings, "WS_IMPORTS_MAX_UNCOMPRESSED_SIZE_BYTES", 5 * 1024**3)
    if result.uncompressed_size > max_size:
        raise ImportExtractedSizeExceededError(
            f"Extracted size {result.uncompressed_size} bytes exceeds limit of {max_size} bytes",
            details=result.to_dict(),
        )

    # File count
    max_count = getattr(settings, "WS_IMPORTS_MAX_FILE_COUNT", 100000)
    if result.file_count > max_count:
        raise ImportFileCountExceededError(
            f"File count {result.file_count} exceeds limit of {max_count}",
            details=result.to_dict(),
        )

    # Single file size
    max_single = getattr(settings, "WS_IMPORTS_MAX_SINGLE_FILE_SIZE_BYTES", 1024**3)
    if result.max_single_file_size > max_single:
        raise ImportExtractedSizeExceededError(
            f"Single file size {result.max_single_file_size} bytes exceeds limit of {max_single} bytes",
            details=result.to_dict(),
        )

    # Path depth
    max_depth = getattr(settings, "WS_IMPORTS_MAX_PATH_DEPTH", 30)
    if result.max_path_depth > max_depth:
        raise ImportPathDepthExceededError(
            f"Path depth {result.max_path_depth} exceeds limit of {max_depth}",
            details=result.to_dict(),
        )

    # Nested archives
    if result.has_nested_archives:
        if allow_notion_nested_zips:
            # Check if all nested zips match Notion's pattern
            forbidden = [name for name in result.nested_archive_names if NOTION_NESTED_ZIP_PATTERN not in name]
            if forbidden:
                raise ImportNestedArchiveError(
                    f"Archive contains forbidden nested archives: {forbidden[:5]}",
                    details=result.to_dict(),
                )
        else:
            raise ImportNestedArchiveError(
                f"Archive contains nested archives: {result.nested_archive_names[:5]}",
                details=result.to_dict(),
            )


def inspect_and_validate_archive(
    file_path: str | Path,
    allow_notion_nested_zips: bool = True,
) -> ArchiveInspectionResult:
    """
    Convenience function that inspects and validates in one call.

    Args:
        file_path: Path to the zip file.
        allow_notion_nested_zips: If True, allows Notion's ExportBlock patterns.

    Returns:
        ArchiveInspectionResult if validation passes.

    Raises:
        ImportInvalidZipError: If file is not a valid zip or has path issues.
        ImportArchiveBombError subclass: If any safety threshold is exceeded.
    """
    result = inspect_archive(file_path)
    validate_archive_safety(result, allow_notion_nested_zips=allow_notion_nested_zips)
    return result

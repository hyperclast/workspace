/**
 * Performance Configuration
 *
 * Centralized thresholds for large document handling.
 * All performance-related constants should be defined here
 * to ensure consistent behavior across features.
 */

// Line-based thresholds (for features that iterate lines)
// Documents over this threshold disable full-document scans
export const LARGE_DOC_LINES = 10_000;

// Byte-based thresholds (for overall file size detection)
// LARGE: Show indicator, still process most decorations
// HUGE: Minimal decorations only
export const LARGE_FILE_BYTES = 1 * 1024 * 1024; // 1 MB
export const HUGE_FILE_BYTES = 10 * 1024 * 1024; // 10 MB

// Feature-specific line limits
// These match LARGE_DOC_LINES but are named for clarity in specific contexts
export const TABLE_SCAN_LIMIT_LINES = LARGE_DOC_LINES;
export const SECTION_SCAN_LIMIT_LINES = LARGE_DOC_LINES;
export const CODE_FENCE_SCAN_LIMIT_LINES = LARGE_DOC_LINES;

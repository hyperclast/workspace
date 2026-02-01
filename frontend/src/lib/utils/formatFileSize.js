/**
 * Format a file size in bytes to a human-readable string.
 *
 * @param {number|null|undefined} bytes - The file size in bytes
 * @param {Object} [options] - Formatting options
 * @param {boolean} [options.compact=false] - If true, returns rounded integers and empty string for zero
 * @returns {string} Formatted file size (e.g., "1.5 MB" or "2 KB" in compact mode)
 */
export function formatFileSize(bytes, options = {}) {
  const { compact = false } = options;

  if (bytes == null || bytes <= 0) {
    return compact ? "" : "0 B";
  }

  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    const kb = bytes / 1024;
    return compact ? `${Math.round(kb)} KB` : `${kb.toFixed(1)} KB`;
  }

  if (bytes < 1024 * 1024 * 1024) {
    const mb = bytes / (1024 * 1024);
    return compact ? `${Math.round(mb)} MB` : `${mb.toFixed(1)} MB`;
  }

  const gb = bytes / (1024 * 1024 * 1024);
  return compact ? `${Math.round(gb)} GB` : `${gb.toFixed(1)} GB`;
}

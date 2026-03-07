/**
 * Time formatting utilities for rewind timeline.
 * Pure functions, no dependencies.
 */

/**
 * Format a date string as a relative time.
 * @param {string} dateString - ISO date string
 * @returns {string} e.g., "2m ago", "1h ago", "Yesterday", or "Mar 5"
 */
export function formatRelativeTime(dateString) {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);

  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;

  // Check if yesterday
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return "Yesterday";
  }

  // Format as short date
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/**
 * Get a day group label for a date.
 * @param {Date} date
 * @returns {string} "Today", "Yesterday", or formatted date
 */
function getDayLabel(date) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const dateDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const diffDays = Math.floor((today - dateDay) / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  return date.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

/**
 * Group rewind entries by day.
 * @param {Array<{created: string}>} entries
 * @returns {Array<{label: string, entries: Array}>}
 */
export function groupByDay(entries) {
  const groups = [];
  let currentLabel = null;
  let currentEntries = [];

  for (const entry of entries) {
    const date = new Date(entry.created);
    const label = getDayLabel(date);

    if (label !== currentLabel) {
      if (currentEntries.length > 0) {
        groups.push({ label: currentLabel, entries: currentEntries });
      }
      currentLabel = label;
      currentEntries = [entry];
    } else {
      currentEntries.push(entry);
    }
  }

  if (currentEntries.length > 0) {
    groups.push({ label: currentLabel, entries: currentEntries });
  }

  return groups;
}

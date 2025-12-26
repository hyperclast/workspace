/**
 * Validation utilities for form inputs
 */

const USERNAME_PATTERN = /^[a-zA-Z0-9._-]+$/;

export function validateUsername(value) {
  if (!value || !value.trim()) {
    return { valid: false, error: "Username is required" };
  }

  const trimmed = value.trim();

  if (trimmed.length > 20) {
    return { valid: false, error: "Username must be 20 characters or less" };
  }

  if (!USERNAME_PATTERN.test(trimmed)) {
    return {
      valid: false,
      error: "Username can only contain letters, numbers, periods, hyphens, and underscores",
    };
  }

  return { valid: true };
}

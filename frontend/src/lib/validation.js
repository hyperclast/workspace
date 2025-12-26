/**
 * Validation utilities for user inputs.
 * These validations mirror backend validation rules to provide instant feedback.
 */

const INVALID_NAME_CHARS = /[/\\:*?"<>|]/;
const INVALID_NAME_CHARS_DISPLAY = '/ \\ : * ? " < > |';

/**
 * Validate a project name for safe filesystem usage.
 * @param {string} name - The project name to validate
 * @returns {{ valid: boolean, error?: string }} Validation result
 */
export function validateProjectName(name) {
  if (!name || !name.trim()) {
    return { valid: false, error: "Project name is required" };
  }

  const trimmed = name.trim();

  if (trimmed.length > 255) {
    return { valid: false, error: "Project name cannot exceed 255 characters" };
  }

  if (INVALID_NAME_CHARS.test(trimmed)) {
    return {
      valid: false,
      error: `Project name cannot contain ${INVALID_NAME_CHARS_DISPLAY}`,
    };
  }

  return { valid: true };
}

/**
 * Check if a string contains invalid filename characters.
 * @param {string} str - The string to check
 * @returns {boolean} True if invalid characters are found
 */
export function hasInvalidNameChars(str) {
  return INVALID_NAME_CHARS.test(str);
}

/**
 * Get the list of invalid characters for display.
 * @returns {string} Space-separated list of invalid characters
 */
export function getInvalidNameCharsDisplay() {
  return INVALID_NAME_CHARS_DISPLAY;
}

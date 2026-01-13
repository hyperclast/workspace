/**
 * Demo mode utilities
 *
 * Demo mode allows users to try the editor without logging in.
 * All features work the same, but data is local-only and mutations prompt signup.
 */

import { showToast } from "../lib/toast.js";

/**
 * Check if the app is running in demo mode.
 * Set by Django template via window._isDemoMode
 */
export function isDemoMode() {
  return window._isDemoMode === true;
}

/**
 * Error thrown when a demo user attempts a mutation action
 */
export class DemoModeError extends Error {
  constructor(message) {
    super(message);
    this.name = "DemoModeError";
  }
}

/**
 * Show a friendly prompt encouraging the user to sign up.
 * Used when they try to do something that requires an account.
 */
export function showDemoPrompt(action = "do that") {
  showToast(`Sign up to ${action}`, "info", {
    action: {
      label: "Sign up free",
      onClick: () => {
        window.location.href = "/signup";
      },
    },
    duration: 5000,
  });
}

/**
 * Navigate to signup page
 */
export function goToSignup() {
  window.location.href = "/signup";
}

/**
 * Navigate to login page
 */
export function goToLogin() {
  window.location.href = "/login";
}

/**
 * Store a filetype override for a demo page.
 * This persists across page reloads within the session.
 */
export function setDemoFiletype(pageId, filetype) {
  try {
    sessionStorage.setItem(`demo-filetype-${pageId}`, filetype);
  } catch {
    // sessionStorage may be unavailable in some contexts
  }
}

/**
 * Get a filetype override for a demo page, if any.
 */
export function getDemoFiletype(pageId) {
  try {
    return sessionStorage.getItem(`demo-filetype-${pageId}`);
  } catch {
    return null;
  }
}

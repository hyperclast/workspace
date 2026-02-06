/**
 * Application configuration
 *
 * Single-origin setup: Django serves both API and frontend static files.
 * All API requests use relative URLs (same origin).
 */

// Layout breakpoint: below this width, sidebars use overlay mode.
// Keep in sync with @media (max-width: 1024px) in style.css.
export const SIDEBAR_OVERLAY_BREAKPOINT = 1024;

// API base URL is always empty string in single-origin setup
export const API_BASE_URL = "";

// WebSocket URL for collaboration - derive from current location
export const WS_BASE_URL = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${
  window.location.host
}`;

// Extract host for WebSocket (without protocol)
export const WS_HOST = WS_BASE_URL.replace(/^wss?:\/\//, "");

// CSRF token is injected by Django template
export function getCsrfToken() {
  return window._csrfToken || null;
}

// User authentication state
export function getUserInfo() {
  return {
    isAuthenticated: window._userIsAuthenticated || false,
    user: window._userInfo || null,
  };
}

// Feature flags from Django settings
export function getFeatureFlags() {
  return window._featureFlags || {};
}

export function isFeatureEnabled(featureName) {
  const flags = getFeatureFlags();
  return !!flags[featureName];
}

export function getPrivateFeatures() {
  const flags = getFeatureFlags();
  return flags.privateFeatures || [];
}

export function isPrivateFeatureEnabled(featureName) {
  return getPrivateFeatures().includes(featureName);
}

export function getPrivateConfig() {
  const flags = getFeatureFlags();
  return flags.privateConfig || {};
}

export function getBrandName() {
  const flags = getFeatureFlags();
  return flags.brandName || "Hyperclast";
}

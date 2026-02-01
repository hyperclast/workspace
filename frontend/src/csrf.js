/**
 * CSRF Token Utilities
 *
 * Django expects the CSRF token to be sent in the X-CSRFToken header
 * for all mutating requests (POST, PUT, PATCH, DELETE).
 */

import {
  getAuthState,
  markLoggedOut,
  markLoginToastShown,
  getLoginUrl,
} from "./lib/stores/auth.js";
import { showToast } from "./lib/stores/toast.svelte.js";

// Client identification for telemetry
const CLIENT_NAME = "web";
const CLIENT_VERSION = __APP_VERSION__; // Injected by Vite from package.json

/**
 * Detect the operating system from navigator.platform.
 * @returns {string} OS identifier: darwin, windows, linux, or unknown
 */
function detectOS() {
  const platform = navigator.platform || "";
  if (platform.includes("Mac")) return "darwin";
  if (platform.includes("Win")) return "windows";
  if (platform.includes("Linux")) return "linux";
  return "unknown";
}

/**
 * Build the X-Hyperclast-Client header value.
 * Format: client=web; version=1.0.0; os=darwin; arch=unknown
 * @returns {string}
 */
function buildClientHeader() {
  return `client=${CLIENT_NAME}; version=${CLIENT_VERSION}; os=${detectOS()}; arch=unknown`;
}

/**
 * Get CSRF token from cookie.
 * Django sets this cookie when CSRF protection is enabled.
 */
export function getCsrfToken() {
  const name = "csrftoken";
  const cookies = document.cookie.split(";");

  for (let cookie of cookies) {
    cookie = cookie.trim();
    if (cookie.startsWith(name + "=")) {
      return cookie.substring(name.length + 1);
    }
  }

  return null;
}

/**
 * Enhanced fetch that automatically includes CSRF token for mutating requests.
 * Use this instead of the native fetch() for all API calls.
 *
 * @param {string} url - The URL to fetch
 * @param {RequestInit} options - Fetch options
 * @returns {Promise<Response>}
 */
export async function csrfFetch(url, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const isMutatingRequest = ["POST", "PUT", "PATCH", "DELETE"].includes(method);

  // Clone options to avoid mutating the original
  const enhancedOptions = {
    ...options,
    credentials: "same-origin",
    headers: {
      ...options.headers,
      "X-Hyperclast-Client": buildClientHeader(),
    },
  };

  // Add CSRF token header for mutating requests
  if (isMutatingRequest) {
    const csrfToken = getCsrfToken();

    if (csrfToken) {
      enhancedOptions.headers["X-CSRFToken"] = csrfToken;
    } else {
      console.warn("CSRF token not found in cookies. Request may fail.");
    }
  }

  const response = await fetch(url, enhancedOptions);

  // Intercept 401 responses
  if (response.status === 401) {
    const { isLoggedOut, loginToastShown } = getAuthState();

    if (!isLoggedOut) {
      markLoggedOut();
      window.dispatchEvent(
        new CustomEvent("authStateChanged", {
          detail: { isAuthenticated: false },
        })
      );
    }

    if (!loginToastShown) {
      markLoginToastShown();
      showToast("You are not logged in", "error", {
        action: {
          label: "Log in",
          onClick: () => {
            window.location.href = getLoginUrl();
          },
        },
        duration: 0,
      });
    }
  }

  return response;
}

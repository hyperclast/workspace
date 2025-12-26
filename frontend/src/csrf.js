/**
 * CSRF Token Utilities
 *
 * Django expects the CSRF token to be sent in the X-CSRFToken header
 * for all mutating requests (POST, PUT, PATCH, DELETE).
 */

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
  const enhancedOptions = { ...options };

  // Add CSRF token header for mutating requests
  if (isMutatingRequest) {
    const csrfToken = getCsrfToken();

    if (csrfToken) {
      enhancedOptions.headers = {
        ...enhancedOptions.headers,
        "X-CSRFToken": csrfToken,
      };
    } else {
      console.warn("CSRF token not found in cookies. Request may fail.");
    }
  }

  return fetch(url, enhancedOptions);
}

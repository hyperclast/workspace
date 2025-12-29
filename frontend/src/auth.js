/**
 * Authentication Service
 * Handles login, signup, logout, and session management
 */

import { API_BASE_URL } from "./config.js";
import { getCsrfToken } from "./csrf.js";

/**
 * Make authenticated API request to the auth backend
 * @param {string} endpoint - The API endpoint (e.g., "/auth/session")
 * @param {RequestInit} options - Fetch options
 * @returns {Promise<Response>}
 */
async function authFetch(endpoint, options = {}) {
  const csrfToken = getCsrfToken();

  const response = await fetch(`${API_BASE_URL}/api/browser/v1${endpoint}`, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken || "",
      ...options.headers,
    },
    ...options,
  });

  return response;
}

/**
 * Get current session status
 * @returns {Promise<{isAuthenticated: boolean, user: object|null}>}
 */
export async function getSession() {
  try {
    const response = await authFetch("/auth/session");

    if (response.ok) {
      const data = await response.json();
      return {
        isAuthenticated: data.meta?.is_authenticated || false,
        user: data.data?.user || null,
      };
    }

    return { isAuthenticated: false, user: null };
  } catch (error) {
    console.error("Failed to get session:", error);
    return { isAuthenticated: false, user: null };
  }
}

/**
 * Login with email and password
 * @param {string} email - User email
 * @param {string} password - User password
 * @returns {Promise<{success: boolean, user?: object, error?: string}>}
 */
export async function login(email, password) {
  try {
    const response = await authFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();

    // Check if login was successful
    // Backend returns status 200 with meta.is_authenticated on success
    if (response.ok && data.meta?.is_authenticated) {
      return { success: true, user: data.data?.user };
    }

    // If response is 200 but not authenticated, or other status codes
    if (!response.ok || !data.meta?.is_authenticated) {
      // Extract error messages from response
      const errors = data.errors || [];
      const errorMessage = errors.map((e) => e.message).join(". ") || "Login failed";
      return { success: false, error: errorMessage };
    }

    return { success: false, error: "Login failed" };
  } catch (error) {
    console.error("Login error:", error);
    return { success: false, error: "Network error. Please try again." };
  }
}

/**
 * Sign up with email and password
 * @param {string} email - User email
 * @param {string} password - User password
 * @returns {Promise<{success: boolean, user?: object, error?: string}>}
 */
export async function signup(email, password) {
  try {
    const response = await authFetch("/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();

    // Check if signup was successful
    // Backend returns status 200 with meta.is_authenticated on success
    if (response.ok && data.meta?.is_authenticated) {
      return { success: true, user: data.data?.user };
    }

    // If response is 200 but not authenticated, or other status codes
    if (!response.ok || !data.meta?.is_authenticated) {
      // Extract error messages from response
      const errors = data.errors || [];
      const errorMessage = errors.map((e) => e.message).join(". ") || "Signup failed";
      return { success: false, error: errorMessage };
    }

    return { success: false, error: "Signup failed" };
  } catch (error) {
    console.error("Signup error:", error);
    return { success: false, error: "Network error. Please try again." };
  }
}

/**
 * Logout the current user
 * @returns {Promise<boolean>} - True if logout was successful
 */
export async function logout() {
  try {
    const response = await authFetch("/auth/session", {
      method: "DELETE",
    });

    return response.ok;
  } catch (error) {
    console.error("Logout error:", error);
    return false;
  }
}

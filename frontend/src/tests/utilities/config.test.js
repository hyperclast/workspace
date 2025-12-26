import { describe, test, expect, beforeEach, afterEach } from "vitest";
import {
  API_BASE_URL,
  WS_BASE_URL,
  WS_HOST,
  getCsrfToken,
  getUserInfo,
} from "../../config.js";

describe("config - constants", () => {
  test("API_BASE_URL is defined and is empty string for single-origin setup", () => {
    expect(API_BASE_URL).toBeDefined();
    expect(API_BASE_URL).toBe("");
  });

  test("WS_BASE_URL is defined and uses correct protocol", () => {
    expect(WS_BASE_URL).toBeDefined();

    // Should use ws:// or wss:// protocol
    expect(WS_BASE_URL).toMatch(/^wss?:\/\//);

    // Should include the host
    expect(WS_BASE_URL).toContain(window.location.host);
  });

  test("WS_BASE_URL uses wss:// when page is served over https://", () => {
    // This test validates the logic, but actual protocol depends on test environment
    const isHttps = window.location.protocol === "https:";
    const expectedProtocol = isHttps ? "wss:" : "ws:";

    expect(WS_BASE_URL.startsWith(expectedProtocol)).toBe(true);
  });

  test("WS_HOST is defined and matches host without protocol", () => {
    expect(WS_HOST).toBeDefined();

    // Should not contain protocol
    expect(WS_HOST).not.toMatch(/^wss?:\/\//);

    // Should be the host from WS_BASE_URL
    const expectedHost = WS_BASE_URL.replace(/^wss?:\/\//, "");
    expect(WS_HOST).toBe(expectedHost);
  });

  test("config values are accessible (not frozen or restricted)", () => {
    // Just verify we can read them
    expect(() => {
      const _baseUrl = API_BASE_URL;
      const _wsUrl = WS_BASE_URL;
      const _wsHost = WS_HOST;
    }).not.toThrow();
  });
});

describe("config - getCsrfToken", () => {
  let originalCsrfToken;

  beforeEach(() => {
    originalCsrfToken = window._csrfToken;
  });

  afterEach(() => {
    window._csrfToken = originalCsrfToken;
  });

  test("returns CSRF token from window._csrfToken when set", () => {
    window._csrfToken = "test-csrf-token-123";

    const token = getCsrfToken();

    expect(token).toBe("test-csrf-token-123");
  });

  test("returns null when window._csrfToken is not set", () => {
    delete window._csrfToken;

    const token = getCsrfToken();

    expect(token).toBeNull();
  });

  test("returns null when window._csrfToken is undefined", () => {
    window._csrfToken = undefined;

    const token = getCsrfToken();

    expect(token).toBeNull();
  });
});

describe("config - getUserInfo", () => {
  let originalUserIsAuthenticated;
  let originalUserInfo;

  beforeEach(() => {
    originalUserIsAuthenticated = window._userIsAuthenticated;
    originalUserInfo = window._userInfo;
  });

  afterEach(() => {
    window._userIsAuthenticated = originalUserIsAuthenticated;
    window._userInfo = originalUserInfo;
  });

  test("returns authenticated state when user is authenticated", () => {
    window._userIsAuthenticated = true;
    window._userInfo = {
      id: 1,
      email: "user@example.com",
      name: "Test User",
    };

    const userInfo = getUserInfo();

    expect(userInfo.isAuthenticated).toBe(true);
    expect(userInfo.user).toEqual({
      id: 1,
      email: "user@example.com",
      name: "Test User",
    });
  });

  test("returns unauthenticated state when user is not authenticated", () => {
    window._userIsAuthenticated = false;
    window._userInfo = null;

    const userInfo = getUserInfo();

    expect(userInfo.isAuthenticated).toBe(false);
    expect(userInfo.user).toBeNull();
  });

  test("defaults to unauthenticated when window globals are not set", () => {
    delete window._userIsAuthenticated;
    delete window._userInfo;

    const userInfo = getUserInfo();

    expect(userInfo.isAuthenticated).toBe(false);
    expect(userInfo.user).toBeNull();
  });

  test("returns user object with all expected fields", () => {
    window._userIsAuthenticated = true;
    window._userInfo = {
      id: 42,
      email: "admin@test.com",
      name: "Admin User",
      role: "admin",
    };

    const userInfo = getUserInfo();

    expect(userInfo.user).toHaveProperty("id");
    expect(userInfo.user).toHaveProperty("email");
    expect(userInfo.user).toHaveProperty("name");
    expect(userInfo.user.id).toBe(42);
  });

  test("handles partial user info gracefully", () => {
    window._userIsAuthenticated = true;
    window._userInfo = { id: 1 }; // Minimal user info

    const userInfo = getUserInfo();

    expect(userInfo.isAuthenticated).toBe(true);
    expect(userInfo.user).toEqual({ id: 1 });
  });
});

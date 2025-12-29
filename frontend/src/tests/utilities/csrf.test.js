import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import { getCsrfToken, csrfFetch } from "../../csrf.js";

describe("getCsrfToken", () => {
  // Store original cookie to restore after tests
  let originalCookie;

  beforeEach(() => {
    originalCookie = document.cookie;
    // Clear all cookies
    document.cookie.split(";").forEach((cookie) => {
      const name = cookie.split("=")[0].trim();
      document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
    });
  });

  afterEach(() => {
    // Restore original cookie
    document.cookie = originalCookie;
  });

  test("reads csrftoken from cookie", () => {
    document.cookie = "csrftoken=abc123def456";

    const token = getCsrfToken();

    expect(token).toBe("abc123def456");
  });

  test("returns null if cookie not set", () => {
    // No cookie set
    const token = getCsrfToken();

    expect(token).toBeNull();
  });

  test("handles multiple cookies and finds csrftoken", () => {
    document.cookie = "sessionid=session123";
    document.cookie = "csrftoken=mytoken";
    document.cookie = "othercookie=value";

    const token = getCsrfToken();

    expect(token).toBe("mytoken");
  });

  test("handles cookies with spaces around them", () => {
    // Simulate browser adding spaces in cookie string
    // When document.cookie is set, the browser normalizes it
    document.cookie = "csrftoken=token_with_spaces";

    const token = getCsrfToken();

    // The implementation trims the cookie entry but not the value itself
    expect(token).toBe("token_with_spaces");
  });

  test("returns first csrftoken if multiple exist", () => {
    // This shouldn't happen normally, but test edge case
    document.cookie = "csrftoken=first_token";
    document.cookie = "csrftoken=second_token";

    const token = getCsrfToken();

    // Should return one of them (likely the first found)
    expect(token).toBeTruthy();
    expect(typeof token).toBe("string");
  });

  test("handles cookie with special characters in token", () => {
    const specialToken = "abc-123_DEF.456";
    document.cookie = `csrftoken=${specialToken}`;

    const token = getCsrfToken();

    expect(token).toBe(specialToken);
  });
});

describe("csrfFetch", () => {
  let fetchSpy;

  beforeEach(() => {
    // Mock global fetch
    fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    // Set a CSRF token
    document.cookie = "csrftoken=test_csrf_token_123";
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  test("includes X-CSRFToken header for POST requests", async () => {
    await csrfFetch("/api/test", {
      method: "POST",
      body: JSON.stringify({ data: "test" }),
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/test",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "X-CSRFToken": "test_csrf_token_123",
        }),
      })
    );
  });

  test("includes X-CSRFToken header for PUT requests", async () => {
    await csrfFetch("/api/test", { method: "PUT" });

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/test",
      expect.objectContaining({
        headers: expect.objectContaining({
          "X-CSRFToken": "test_csrf_token_123",
        }),
      })
    );
  });

  test("includes X-CSRFToken header for PATCH requests", async () => {
    await csrfFetch("/api/test", { method: "PATCH" });

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/test",
      expect.objectContaining({
        headers: expect.objectContaining({
          "X-CSRFToken": "test_csrf_token_123",
        }),
      })
    );
  });

  test("includes X-CSRFToken header for DELETE requests", async () => {
    await csrfFetch("/api/test", { method: "DELETE" });

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/test",
      expect.objectContaining({
        headers: expect.objectContaining({
          "X-CSRFToken": "test_csrf_token_123",
        }),
      })
    );
  });

  test("does not include X-CSRFToken header for GET requests", async () => {
    await csrfFetch("/api/test", { method: "GET" });

    const callArgs = fetchSpy.mock.calls[0][1];
    expect(callArgs.headers).toBeUndefined();
  });

  test("does not include X-CSRFToken header when no method specified (defaults to GET)", async () => {
    await csrfFetch("/api/test");

    const callArgs = fetchSpy.mock.calls[0][1];
    expect(callArgs.headers).toBeUndefined();
  });

  test("preserves existing headers when adding CSRF token", async () => {
    await csrfFetch("/api/test", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer token",
      },
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/test",
      expect.objectContaining({
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Authorization: "Bearer token",
          "X-CSRFToken": "test_csrf_token_123",
        }),
      })
    );
  });

  test("passes through all other fetch options unchanged", async () => {
    await csrfFetch("/api/test", {
      method: "POST",
      body: JSON.stringify({ test: "data" }),
      credentials: "include",
      mode: "cors",
      cache: "no-cache",
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/test",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ test: "data" }),
        credentials: "include",
        mode: "cors",
        cache: "no-cache",
      })
    );
  });

  test("handles POST request when CSRF token is missing", async () => {
    // Clear the CSRF token
    document.cookie = "csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT";

    const consoleSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    await csrfFetch("/api/test", { method: "POST" });

    // Should log a warning
    expect(consoleSpy).toHaveBeenCalledWith(expect.stringContaining("CSRF token not found"));

    // Should still make the request (without the header)
    expect(fetchSpy).toHaveBeenCalled();

    consoleSpy.mockRestore();
  });

  test("handles case-insensitive method names", async () => {
    await csrfFetch("/api/test", { method: "post" });

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/test",
      expect.objectContaining({
        headers: expect.objectContaining({
          "X-CSRFToken": "test_csrf_token_123",
        }),
      })
    );
  });

  test("does not mutate original options object", async () => {
    const originalOptions = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    };

    const optionsCopy = { ...originalOptions };

    await csrfFetch("/api/test", originalOptions);

    // Original options should be unchanged
    expect(originalOptions).toEqual(optionsCopy);
  });

  test("returns the fetch promise", async () => {
    const result = await csrfFetch("/api/test", { method: "GET" });

    expect(result).toBeInstanceOf(Response);
    const data = await result.json();
    expect(data).toEqual({ success: true });
  });
});

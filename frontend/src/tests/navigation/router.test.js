import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import { getPageIdFromPath, navigate } from "../../router.js";

describe("router - getPageIdFromPath", () => {
  test("extracts page ID from /pages/{id}/ URL", () => {
    expect(getPageIdFromPath("/pages/abc123/")).toBe("abc123");
  });

  test("extracts page ID without trailing slash", () => {
    expect(getPageIdFromPath("/pages/abc123")).toBe("abc123");
  });

  test("returns null for non-page paths", () => {
    expect(getPageIdFromPath("/settings/")).toBeNull();
    expect(getPageIdFromPath("/login")).toBeNull();
    expect(getPageIdFromPath("/")).toBeNull();
  });

  test("handles complex page IDs", () => {
    expect(getPageIdFromPath("/pages/a1b2c3d4e5/")).toBe("a1b2c3d4e5");
    expect(getPageIdFromPath("/pages/page-with-dashes/")).toBe("page-with-dashes");
  });
});

describe("router - path normalization", () => {
  function normalizePath(path) {
    if (path !== "/" && !path.endsWith("/")) {
      return path + "/";
    }
    return path;
  }

  test("paths without trailing slash should be normalized to have trailing slash", () => {
    expect(normalizePath("/settings")).toBe("/settings/");
    expect(normalizePath("/login")).toBe("/login/");
    expect(normalizePath("/signup")).toBe("/signup/");
    expect(normalizePath("/invitation")).toBe("/invitation/");
    expect(normalizePath("/reset-password")).toBe("/reset-password/");
    expect(normalizePath("/forgot-password")).toBe("/forgot-password/");
  });

  test("paths with trailing slash should remain unchanged", () => {
    expect(normalizePath("/settings/")).toBe("/settings/");
    expect(normalizePath("/login/")).toBe("/login/");
    expect(normalizePath("/pages/abc123/")).toBe("/pages/abc123/");
  });

  test("root path should not be modified", () => {
    expect(normalizePath("/")).toBe("/");
  });

  test("routes with and without trailing slash normalize to the same path", () => {
    const routePairs = [
      ["/settings", "/settings/"],
      ["/login", "/login/"],
      ["/signup", "/signup/"],
      ["/invitation", "/invitation/"],
      ["/reset-password", "/reset-password/"],
      ["/forgot-password", "/forgot-password/"],
    ];

    for (const [withoutSlash, withSlash] of routePairs) {
      expect(normalizePath(withoutSlash)).toBe(normalizePath(withSlash));
      expect(normalizePath(withoutSlash)).toBe(withSlash);
    }
  });
});

describe("router - navigate function", () => {
  let pushStateSpy;
  let originalPathname;

  beforeEach(() => {
    pushStateSpy = vi.spyOn(window.history, "pushState").mockImplementation(() => {});
    originalPathname = window.location.pathname;
  });

  afterEach(() => {
    pushStateSpy.mockRestore();
    Object.defineProperty(window, "location", {
      value: { ...window.location, pathname: originalPathname },
      writable: true,
    });
  });

  test("navigate adds trailing slash to path without one", () => {
    navigate("/settings");

    expect(pushStateSpy).toHaveBeenCalledWith({}, "", "/settings/");
  });

  test("navigate preserves trailing slash when already present", () => {
    navigate("/settings/");

    expect(pushStateSpy).toHaveBeenCalledWith({}, "", "/settings/");
  });

  test("navigate does not add trailing slash to root path", () => {
    navigate("/");

    expect(pushStateSpy).toHaveBeenCalledWith({}, "", "/");
  });

  test("navigate normalizes all route paths", () => {
    const testCases = [
      ["/login", "/login/"],
      ["/signup", "/signup/"],
      ["/settings", "/settings/"],
      ["/forgot-password", "/forgot-password/"],
      ["/reset-password", "/reset-password/"],
    ];

    for (const [input, expected] of testCases) {
      pushStateSpy.mockClear();
      navigate(input);
      expect(pushStateSpy).toHaveBeenCalledWith({}, "", expected);
    }
  });
});

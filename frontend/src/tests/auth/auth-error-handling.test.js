import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import {
  getAuthState,
  markLoggedOut,
  markLoginToastShown,
  resetAuthState,
  getLoginUrl,
} from "../../lib/stores/auth.js";
import { showToast, getToasts, removeToast } from "../../lib/stores/toast.svelte.js";
import { csrfFetch } from "../../csrf.js";

describe("Auth State Module", () => {
  beforeEach(() => {
    resetAuthState();
  });

  test("initial state is logged in with no toast shown", () => {
    const state = getAuthState();
    expect(state.isLoggedOut).toBe(false);
    expect(state.loginToastShown).toBe(false);
  });

  test("markLoggedOut sets isLoggedOut to true", () => {
    markLoggedOut();
    const state = getAuthState();
    expect(state.isLoggedOut).toBe(true);
  });

  test("markLoginToastShown sets loginToastShown to true", () => {
    markLoginToastShown();
    const state = getAuthState();
    expect(state.loginToastShown).toBe(true);
  });

  test("resetAuthState clears both flags", () => {
    markLoggedOut();
    markLoginToastShown();

    resetAuthState();

    const state = getAuthState();
    expect(state.isLoggedOut).toBe(false);
    expect(state.loginToastShown).toBe(false);
  });

  test("getLoginUrl returns login URL with current path as next parameter", () => {
    // Note: In test environment, window.location is typically empty or "about:blank"
    const url = getLoginUrl();
    expect(url).toContain("/login/?next=");
  });
});

describe("Toast with Action Button", () => {
  beforeEach(() => {
    // Clear any existing toasts
    const toasts = getToasts();
    toasts.forEach((t) => removeToast(t.id));
  });

  afterEach(() => {
    // Clear toasts after each test
    const toasts = getToasts();
    toasts.forEach((t) => removeToast(t.id));
  });

  test("showToast creates toast with action when provided", () => {
    const onClick = vi.fn();

    showToast("Test message", "error", {
      action: { label: "Click me", onClick },
    });

    const toasts = getToasts();
    expect(toasts.length).toBe(1);
    expect(toasts[0].message).toBe("Test message");
    expect(toasts[0].type).toBe("error");
    expect(toasts[0].action).not.toBeNull();
    expect(toasts[0].action.label).toBe("Click me");
  });

  test("action onClick handler is callable", () => {
    const onClick = vi.fn();

    showToast("Test message", "error", {
      action: { label: "Test", onClick },
    });

    const toasts = getToasts();
    toasts[0].action.onClick();

    expect(onClick).toHaveBeenCalledTimes(1);
  });

  test("showToast supports legacy duration parameter", () => {
    vi.useFakeTimers();

    showToast("Test message", "success", 1000);

    expect(getToasts().length).toBe(1);

    vi.advanceTimersByTime(1500);

    expect(getToasts().length).toBe(0);

    vi.useRealTimers();
  });

  test("error toast with duration: 0 does not auto-dismiss", () => {
    vi.useFakeTimers();

    showToast("Error message", "error", { duration: 0 });

    expect(getToasts().length).toBe(1);

    vi.advanceTimersByTime(10000);

    expect(getToasts().length).toBe(1); // Still there

    vi.useRealTimers();
  });

  test("error toast without options defaults to duration: 0", () => {
    vi.useFakeTimers();

    showToast("Error message", "error");

    expect(getToasts().length).toBe(1);

    vi.advanceTimersByTime(10000);

    expect(getToasts().length).toBe(1); // Still there

    vi.useRealTimers();
  });
});

describe("401 Interceptor in csrfFetch", () => {
  let fetchSpy;

  beforeEach(() => {
    resetAuthState();

    // Clear any existing toasts
    const toasts = getToasts();
    toasts.forEach((t) => removeToast(t.id));

    // Set a CSRF token
    document.cookie = "csrftoken=test_csrf_token_123";
  });

  afterEach(() => {
    if (fetchSpy) {
      fetchSpy.mockRestore();
    }

    // Clear toasts after each test
    const toasts = getToasts();
    toasts.forEach((t) => removeToast(t.id));
  });

  test("single 401 response shows login toast", async () => {
    fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Authentication required" }), {
        status: 401,
      })
    );

    const eventHandler = vi.fn();
    window.addEventListener("authStateChanged", eventHandler);

    await csrfFetch("/api/test", { method: "POST" });

    // Should show toast
    const toasts = getToasts();
    expect(toasts.length).toBe(1);
    expect(toasts[0].message).toBe("You are not logged in");
    expect(toasts[0].type).toBe("error");
    expect(toasts[0].action).not.toBeNull();
    expect(toasts[0].action.label).toBe("Log in");

    // Should dispatch authStateChanged event
    expect(eventHandler).toHaveBeenCalled();
    expect(eventHandler.mock.calls[0][0].detail.isAuthenticated).toBe(false);

    // Should update auth state
    const state = getAuthState();
    expect(state.isLoggedOut).toBe(true);
    expect(state.loginToastShown).toBe(true);

    window.removeEventListener("authStateChanged", eventHandler);
  });

  test("multiple simultaneous 401s show only ONE toast (no duplicates)", async () => {
    fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Authentication required" }), {
        status: 401,
      })
    );

    // Fire multiple 401 requests simultaneously
    await Promise.all([
      csrfFetch("/api/test1", { method: "POST" }),
      csrfFetch("/api/test2", { method: "POST" }),
      csrfFetch("/api/test3", { method: "POST" }),
    ]);

    // Should show exactly one toast
    const toasts = getToasts();
    expect(toasts.length).toBe(1);
  });

  test("authStateChanged event is dispatched only once for multiple 401s", async () => {
    fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Authentication required" }), {
        status: 401,
      })
    );

    const eventHandler = vi.fn();
    window.addEventListener("authStateChanged", eventHandler);

    await Promise.all([
      csrfFetch("/api/test1", { method: "POST" }),
      csrfFetch("/api/test2", { method: "POST" }),
    ]);

    // Event should be dispatched only once
    expect(eventHandler).toHaveBeenCalledTimes(1);

    window.removeEventListener("authStateChanged", eventHandler);
  });

  test("200 response does not trigger auth handling", async () => {
    fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ success: true }), {
        status: 200,
      })
    );

    await csrfFetch("/api/test", { method: "POST" });

    const toasts = getToasts();
    expect(toasts.length).toBe(0);

    const state = getAuthState();
    expect(state.isLoggedOut).toBe(false);
  });

  test("403 response does not trigger auth handling", async () => {
    fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Forbidden" }), {
        status: 403,
      })
    );

    await csrfFetch("/api/test", { method: "POST" });

    const toasts = getToasts();
    expect(toasts.length).toBe(0);

    const state = getAuthState();
    expect(state.isLoggedOut).toBe(false);
  });

  test("login action button navigates to login URL", async () => {
    fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Authentication required" }), {
        status: 401,
      })
    );

    // Mock window.location.href assignment
    const originalLocation = window.location;
    delete window.location;
    window.location = { ...originalLocation, href: "", pathname: "/pages/test123/", search: "" };

    await csrfFetch("/api/test", { method: "POST" });

    const toasts = getToasts();
    const loginAction = toasts[0].action;

    // Call the onClick handler
    loginAction.onClick();

    // Should set location to login URL with next parameter
    expect(window.location.href).toContain("/login/");
    expect(window.location.href).toContain("next=");

    // Restore window.location
    window.location = originalLocation;
  });
});

describe("Connection Status Updates", () => {
  test("authStateChanged event triggers status update listener", () => {
    const statusHandler = vi.fn();

    // Simulate the event listener that main.js sets up
    const authHandler = (event) => {
      if (!event.detail.isAuthenticated) {
        statusHandler("unauthorized");
      }
    };

    window.addEventListener("authStateChanged", authHandler);

    // Dispatch auth state change
    window.dispatchEvent(
      new CustomEvent("authStateChanged", {
        detail: { isAuthenticated: false },
      })
    );

    expect(statusHandler).toHaveBeenCalledWith("unauthorized");

    window.removeEventListener("authStateChanged", authHandler);
  });
});

/**
 * subscribeToPageEvents() tests
 *
 * The helper opens a thin WebSocket so pages that skip Yjs collaboration
 * (PDF pages) still receive comment / AI-review broadcasts in real time.
 *
 * These tests stub the global `WebSocket` constructor and assert that
 * server-sent text frames are translated into the right window CustomEvents,
 * that binary frames are ignored, and that cleanup closes the socket.
 */

import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import { subscribeToPageEvents, clearAccessDenied } from "../collaboration.js";

class FakeWebSocket {
  static instances = [];
  static OPEN = 1;
  static CLOSED = 3;

  constructor(url) {
    this.url = url;
    this.readyState = FakeWebSocket.OPEN;
    this.binaryType = "blob";
    this.listeners = { open: [], message: [], close: [], error: [] };
    this.closeCalls = [];
    FakeWebSocket.instances.push(this);
  }

  addEventListener(type, fn) {
    if (this.listeners[type]) this.listeners[type].push(fn);
  }

  emit(type, event) {
    (this.listeners[type] || []).forEach((fn) => fn(event));
  }

  close(code, reason) {
    this.closeCalls.push({ code, reason });
    this.readyState = FakeWebSocket.CLOSED;
  }
}

function captureWindowEvent(type) {
  const events = [];
  const handler = (e) => events.push(e);
  window.addEventListener(type, handler);
  return {
    events,
    cleanup: () => window.removeEventListener(type, handler),
  };
}

describe("subscribeToPageEvents", () => {
  let originalWebSocket;
  let originalLocation;

  beforeEach(() => {
    // Module-scoped state survives across tests; reset so prior access-denied
    // outcomes don't short-circuit the next subscribeToPageEvents call.
    clearAccessDenied();
    FakeWebSocket.instances = [];
    originalWebSocket = globalThis.WebSocket;
    globalThis.WebSocket = FakeWebSocket;
    // Force the helper's protocol/host to be deterministic
    originalLocation = window.location;
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { protocol: "http:", host: "localhost:9800" },
    });
    vi.useFakeTimers();
  });

  afterEach(() => {
    globalThis.WebSocket = originalWebSocket;
    Object.defineProperty(window, "location", { configurable: true, value: originalLocation });
    vi.useRealTimers();
  });

  test("opens a WebSocket to /ws/pages/<id>/", () => {
    subscribeToPageEvents("page-abc");
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].url).toBe("ws://localhost:9800/ws/pages/page-abc/");
    expect(FakeWebSocket.instances[0].binaryType).toBe("arraybuffer");
  });

  test("dispatches commentsUpdated on a comments_updated text frame", () => {
    const cap = captureWindowEvent("commentsUpdated");
    subscribeToPageEvents("page-abc");
    const ws = FakeWebSocket.instances[0];
    ws.emit("message", { data: JSON.stringify({ type: "comments_updated" }) });
    expect(cap.events).toHaveLength(1);
    expect(cap.events[0].detail).toEqual({ pageId: "page-abc" });
    cap.cleanup();
  });

  test("dispatches aiReviewComplete with persona and commentCount", () => {
    const cap = captureWindowEvent("aiReviewComplete");
    subscribeToPageEvents("page-abc");
    const ws = FakeWebSocket.instances[0];
    ws.emit("message", {
      data: JSON.stringify({ type: "ai_review_complete", persona: "socrates", comment_count: 2 }),
    });
    expect(cap.events).toHaveLength(1);
    expect(cap.events[0].detail).toEqual({ persona: "socrates", commentCount: 2 });
    cap.cleanup();
  });

  test("ignores binary frames", () => {
    const cap = captureWindowEvent("commentsUpdated");
    subscribeToPageEvents("page-abc");
    const ws = FakeWebSocket.instances[0];
    ws.emit("message", { data: new ArrayBuffer(8) });
    expect(cap.events).toHaveLength(0);
    cap.cleanup();
  });

  test("ignores malformed JSON without throwing", () => {
    subscribeToPageEvents("page-abc");
    const ws = FakeWebSocket.instances[0];
    expect(() => ws.emit("message", { data: "not json" })).not.toThrow();
  });

  test("closes the socket on access_denied error frame and stops reconnect", () => {
    const cap = captureWindowEvent("collabError");
    subscribeToPageEvents("page-abc");
    const ws = FakeWebSocket.instances[0];
    ws.emit("message", {
      data: JSON.stringify({ type: "error", code: "access_denied", message: "no" }),
    });
    expect(cap.events).toHaveLength(1);
    expect(cap.events[0].detail.code).toBe("access_denied");
    expect(ws.closeCalls.length).toBeGreaterThan(0);
    // Subsequent close events shouldn't trigger reconnect.
    ws.emit("close", { code: 1006 });
    vi.advanceTimersByTime(60000);
    expect(FakeWebSocket.instances).toHaveLength(1);
    cap.cleanup();
  });

  test("dispatches pageAccessRevoked on access_revoked frame", () => {
    const cap = captureWindowEvent("pageAccessRevoked");
    subscribeToPageEvents("page-abc");
    const ws = FakeWebSocket.instances[0];
    ws.emit("message", {
      data: JSON.stringify({ type: "access_revoked", message: "removed" }),
    });
    expect(cap.events).toHaveLength(1);
    expect(cap.events[0].detail.pageId).toBe("page-abc");
    cap.cleanup();
  });

  test("cleanup closes the WebSocket and prevents reconnect", () => {
    const unsubscribe = subscribeToPageEvents("page-abc");
    const ws = FakeWebSocket.instances[0];
    unsubscribe();
    expect(ws.closeCalls).toEqual([{ code: 1000, reason: "Page closed" }]);
    // After cleanup, an unrelated close event should not trigger reconnect.
    ws.emit("close", { code: 1006 });
    vi.advanceTimersByTime(60000);
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  test("reconnects with backoff on unexpected close", () => {
    subscribeToPageEvents("page-abc");
    expect(FakeWebSocket.instances).toHaveLength(1);
    const first = FakeWebSocket.instances[0];
    first.emit("close", { code: 1006 });
    // Backoff is 1000ms initially; advance just past it.
    vi.advanceTimersByTime(1100);
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  test("does not reconnect on auth-error close codes", () => {
    subscribeToPageEvents("page-abc");
    const ws = FakeWebSocket.instances[0];
    ws.emit("close", { code: 4003 });
    vi.advanceTimersByTime(60000);
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  test("returns a no-op cleanup when access was previously denied", () => {
    // First subscription gets denied → marks the page as access-denied.
    subscribeToPageEvents("page-denied");
    const ws = FakeWebSocket.instances[0];
    ws.emit("message", {
      data: JSON.stringify({ type: "error", code: "access_denied", message: "no" }),
    });

    // Second subscription should not open a new socket.
    const before = FakeWebSocket.instances.length;
    const unsubscribe = subscribeToPageEvents("page-denied");
    expect(FakeWebSocket.instances.length).toBe(before);
    expect(typeof unsubscribe).toBe("function");
    unsubscribe(); // must not throw
  });
});

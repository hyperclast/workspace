/**
 * Yjs Collaboration Setup
 * Integrates Yjs CRDT with CodeMirror for real-time collaborative editing
 */
import { yCollab, yUndoManagerKeymap } from "y-codemirror.next";
import { WebsocketProvider } from "y-websocket";
import * as Y from "yjs";
import { keymap } from "@codemirror/view";
import { Prec } from "@codemirror/state";
import { WS_HOST } from "./config.js";

// WebSocket close code 4029 is sent by the consumer for rate-limited connections
// (mirrors WS_CLOSE_RATE_LIMITED in backend/collab/consumers.py).
const WS_CLOSE_RATE_LIMITED = 4029;

// Track pages that have had access denied - don't retry these
const accessDeniedPages = new Set();

// Global error handler to catch Yjs decoding errors
// These can happen when WebSocket messages are corrupted or truncated
window.addEventListener("error", (event) => {
  if (event.message?.includes("Unexpected end of array")) {
    console.error("[Yjs Decode Error] Caught decoding error:", {
      message: event.message,
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
    });
    // Prevent the error from propagating (optional - remove if you want to see it in console)
    // event.preventDefault();
  }
});

/**
 * Pure decision for what `setupCollaborationAsync` should do after
 * the Yjs sync handshake settles. Returns one of:
 *
 * - "denied"            — sync resolver flagged access denied
 * - "hold_rest_timeout" — sync never completed (timeout / null)
 * - "upgrade_to_collab" — synced, server is authoritative
 *
 * Takes only the sync result on purpose: the server is the single
 * writer of the seed (advisory-locked write inside
 * `_seed_ydoc_from_page`), so the post-sync decision is a function of
 * the handshake outcome alone. Anything that read `ytext` or
 * `restContent` here would be tempted to gate the upgrade on local
 * state, which is what produced the content-doubling race the server
 * seed fixed.
 *
 * Synced + empty-ytext is treated as authoritative — a stale REST
 * `details.content` is reconciled to `""` by the consumer when the
 * room actually nets to empty (see `_reconcile_empty_page_content` in
 * `backend/collab/consumers.py`). An earlier iteration held the REST
 * view in that case, but it broke real-time sync for legitimately-
 * emptied pages.
 *
 * @param {{synced?: boolean, accessDenied?: boolean} | null | undefined} syncResult
 * @returns {"denied" | "hold_rest_timeout" | "upgrade_to_collab"}
 */
export function decideAfterSync(syncResult) {
  if (!syncResult) return "hold_rest_timeout";
  if (syncResult.accessDenied) return "denied";
  if (!syncResult.synced) return "hold_rest_timeout";
  return "upgrade_to_collab";
}

/**
 * Create collaboration objects for a page.
 * This should be called BEFORE creating the editor view.
 * @param {string} pageExternalId - The page's external_id (used as room identifier)
 * @param {string} displayName - Display name for the user (username or email)
 * @returns {Object} - { ydoc, provider, ytext, awareness, extension, syncPromise } for use in editor
 */
export function createCollaborationObjects(pageExternalId, displayName = "Anonymous") {
  // Check if we've previously been denied access to this page
  if (accessDeniedPages.has(pageExternalId)) {
    console.warn(
      `Skipping WebSocket connection - access previously denied for page ${pageExternalId}`
    );
    // Return a "dummy" collaboration object that won't try to connect
    const ydoc = new Y.Doc();
    const ytext = ydoc.getText("codemirror");
    return {
      ydoc,
      provider: null,
      ytext,
      awareness: null,
      get extension() {
        return yCollab(ytext, null);
      },
      syncPromise: Promise.resolve({ synced: false, accessDenied: true }),
    };
  }

  // Create a new Yjs document
  const ydoc = new Y.Doc();

  // Get the shared text type (this will sync across all clients)
  const ytext = ydoc.getText("codemirror");

  // Determine WebSocket URL based on environment
  const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${wsProtocol}//${WS_HOST}/ws/pages/${pageExternalId}`;

  console.log("Connecting to WebSocket:", wsUrl);
  console.time("[PERF] WebSocket connect");

  // Create WebSocket provider for syncing
  // Pass empty string as room name since the room ID is already in the URL path
  // Disable resync to avoid unnecessary reconnection delays
  const provider = new WebsocketProvider(wsUrl, "", ydoc, {
    connect: true,
    resyncInterval: -1, // Disable automatic resync (we handle reconnection ourselves)
    maxBackoffTime: 1000, // Reduce max backoff for faster reconnection
  });

  // Setup awareness (for showing who's online, cursors, etc.)
  const awareness = provider.awareness;

  // Set local user info
  awareness.setLocalStateField("user", {
    name: displayName,
    color: getRandomColor(),
  });

  // Track connection attempts for detecting repeated failures
  let connectionAttempts = 0;
  const maxFailedAttempts = 3;

  // Listen to provider events and dispatch custom events for UI updates
  provider.on("status", ({ status }) => {
    console.log("WebSocket status:", status); // 'connecting' | 'connected' | 'disconnected'
    if (status === "connected") {
      console.timeEnd("[PERF] WebSocket connect");
      connectionAttempts = 0; // Reset on successful connection
      window.dispatchEvent(
        new CustomEvent("collabStatus", { detail: { status: "connected", pageId: pageExternalId } })
      );
    }
    if (status === "disconnected") {
      connectionAttempts++;
      // After 3 failed attempts in a row without syncing, assume access is denied
      if (connectionAttempts >= maxFailedAttempts && !provider.synced) {
        console.warn(
          `Multiple connection failures for page ${pageExternalId} - assuming access denied`
        );
        accessDeniedPages.add(pageExternalId);
        provider.shouldConnect = false;
        provider.disconnect();
        window.dispatchEvent(
          new CustomEvent("collabStatus", { detail: { status: "denied", pageId: pageExternalId } })
        );
      } else {
        // Normal disconnection - will attempt to reconnect
        window.dispatchEvent(
          new CustomEvent("collabStatus", { detail: { status: "offline", pageId: pageExternalId } })
        );
      }
    }
  });

  // Track connection errors - stop reconnection on 403 (access denied)
  provider.on("connection-error", (event) => {
    console.error("WebSocket connection-error:", event);
    // y-websocket passes the WebSocket error event, which includes the HTTP response
    // For a 403, we should stop trying to reconnect
    if (event?.target?.url) {
      console.warn("Connection failed to:", event.target.url);
    }
  });

  // Handle WebSocket close codes that indicate we shouldn't retry
  // 4003 = access denied (our custom code)
  // 4001 = access revoked
  // 1008 = policy violation
  provider.on("connection-close", (event) => {
    const code = event?.code;
    const reason = event?.reason;
    console.log("WebSocket close:", { code, reason, wasClean: event?.wasClean });

    // Stop reconnection for permission errors
    const authErrorCodes = [4003, 4001, 1008];
    if (authErrorCodes.includes(code)) {
      console.warn(
        `Access denied (code ${code}) - stopping reconnection attempts for page ${pageExternalId}`
      );
      accessDeniedPages.add(pageExternalId);
      provider.shouldConnect = false;
      provider.disconnect();

      // Broadcast auth state change for UI updates
      window.dispatchEvent(
        new CustomEvent("authStateChanged", {
          detail: { isAuthenticated: false },
        })
      );

      // Update status to unauthorized (not offline)
      window.dispatchEvent(
        new CustomEvent("collabStatus", {
          detail: { status: "unauthorized", pageId: pageExternalId },
        })
      );
    }
  });

  // Track sync state for the caller
  let syncResolved = false;

  // Create a promise that resolves when first sync completes
  const syncPromise = new Promise((resolve) => {
    // Check if already synced (unlikely but possible)
    if (provider.synced) {
      console.log("Already synced, ytext.length=" + ytext.length);
      syncResolved = true;
      resolve({ synced: true });
      return;
    }

    const onSync = (isSynced) => {
      console.log("Sync status:", isSynced ? "synced" : "syncing", "ytext.length=" + ytext.length);
      if (isSynced && !syncResolved) {
        syncResolved = true;
        provider.off("sync", onSync);
        resolve({ synced: true });
      }
    };

    provider.on("sync", onSync);

    // Fallback timeout - resolve but indicate sync didn't complete
    // 10s timeout to handle slow initial WebSocket connections
    setTimeout(() => {
      if (!syncResolved) {
        console.warn(
          "Sync timeout after 10s - provider.synced=" +
            provider.synced +
            ", wsConnected=" +
            (provider.wsconnected || false)
        );
        syncResolved = true;
        provider.off("sync", onSync);
        resolve({ synced: false });
      }
    }, 10000);
  });

  // Listen to awareness changes (who joined/left)
  awareness.on("change", (changes, origin) => {
    try {
      const states = awareness.getStates();
      console.log("Awareness changed, total users:", states.size, "origin:", origin);
    } catch (e) {
      console.error("[Awareness Error] Error in awareness change handler:", e);
    }
  });

  // Listen for custom messages (like access revocation, links updated, errors)
  // The WebSocket provider exposes the underlying WebSocket
  const setupMessageListener = () => {
    if (!provider.ws) return;

    provider.ws.addEventListener("message", (event) => {
      // Check if this is a text message (not binary Yjs sync message)
      if (typeof event.data === "string") {
        try {
          const message = JSON.parse(event.data);

          if (message.type === "error") {
            console.warn(
              `WebSocket error for page ${pageExternalId}:`,
              message.code,
              message.message
            );

            if (message.code === "access_denied" || message.code === "rate_limited") {
              accessDeniedPages.add(pageExternalId);
              provider.shouldConnect = false;

              window.dispatchEvent(
                new CustomEvent("collabError", {
                  detail: {
                    pageId: pageExternalId,
                    code: message.code,
                    message: message.message,
                  },
                })
              );
            }
          } else if (message.type === "access_revoked") {
            console.warn("Access to this page has been revoked");
            accessDeniedPages.add(pageExternalId);
            provider.shouldConnect = false;

            window.dispatchEvent(
              new CustomEvent("pageAccessRevoked", {
                detail: { pageId: pageExternalId, message: message.message },
              })
            );
          } else if (message.type === "links_updated") {
            console.log("Links updated notification received for page:", message.page_id);
            window.dispatchEvent(
              new CustomEvent("linksUpdated", {
                detail: { pageId: message.page_id },
              })
            );
          } else if (message.type === "rewind_created") {
            window.dispatchEvent(
              new CustomEvent("rewindCreated", {
                detail: { pageId: message.page_id, rewind: message.rewind },
              })
            );
          } else if (message.type === "folders_updated") {
            window.dispatchEvent(new CustomEvent("foldersUpdated"));
          } else if (message.type === "comments_updated") {
            window.dispatchEvent(new CustomEvent("commentsUpdated"));
          } else if (message.type === "ai_review_complete") {
            window.dispatchEvent(
              new CustomEvent("aiReviewComplete", {
                detail: { persona: message.persona, commentCount: message.comment_count },
              })
            );
          }
        } catch (e) {
          // Not a JSON message, ignore
        }
      }
    });
  };

  // Setup listener now if WS exists, or when it connects
  setupMessageListener();
  provider.on("status", ({ status }) => {
    if (status === "connected") {
      setupMessageListener();
    }
  });

  // Add debug logging for binary WebSocket messages and fix text message handling
  const setupBinaryMessageDebug = () => {
    if (!provider.ws) return;

    const originalOnMessage = provider.ws.onmessage;
    provider.ws.onmessage = (event) => {
      const isBinary = event.data instanceof ArrayBuffer || event.data instanceof Blob;

      if (isBinary) {
        const size = event.data instanceof ArrayBuffer ? event.data.byteLength : event.data.size;
        console.log("[WS Binary] Received binary message:", size, "bytes");

        // Log first few bytes for debugging if it's an ArrayBuffer
        if (event.data instanceof ArrayBuffer && size > 0) {
          const view = new Uint8Array(event.data);
          const preview = Array.from(view.slice(0, 10))
            .map((b) => b.toString(16).padStart(2, "0"))
            .join(" ");
          console.log("[WS Binary] First bytes:", preview, size > 10 ? "..." : "");
        }

        // Only pass BINARY messages to y-websocket handler
        // Text messages (like links_updated JSON) are handled by setupMessageListener
        if (originalOnMessage) {
          try {
            originalOnMessage.call(provider.ws, event);
          } catch (e) {
            console.error("[WS Binary] Error processing binary message:", e, {
              size: size,
            });
          }
        }
      } else {
        // Text message - log it but DON'T pass to y-websocket (it can't handle text)
        // Our setupMessageListener handles text messages separately via addEventListener
        console.log("[WS Text] Received text message:", event.data?.substring?.(0, 100));
      }
    };
  };

  // Setup binary debug when connected
  provider.on("status", ({ status }) => {
    if (status === "connected") {
      setupBinaryMessageDebug();
    }
  });

  // Listen for ydoc updates to catch any errors
  ydoc.on("update", (update, origin) => {
    console.log("[Ydoc Update] Received update:", update.byteLength, "bytes, origin:", origin);
  });

  console.log("Collaboration objects created for page:", pageExternalId);

  // Create UndoManager for undo/redo with collaborative editing
  const undoManager = new Y.UndoManager(ytext, {
    captureTimeout: 500,
  });

  // Return objects for use in editor and cleanup
  // Extension is created lazily after sync completes to ensure ytext has content
  let _extension = null;
  return {
    ydoc,
    provider,
    ytext,
    awareness,
    undoManager,
    get extension() {
      if (!_extension) {
        // yCollab returns plugins for sync, awareness, and undo tracking
        // but does NOT include the keyboard bindings for undo/redo.
        // We must add yUndoManagerKeymap with high precedence so it
        // intercepts Mod-z before CodeMirror's defaultKeymap.
        const collabPlugins = yCollab(ytext, awareness, { undoManager });
        _extension = [Prec.high(keymap.of(yUndoManagerKeymap)), ...collabPlugins];
        console.log("yCollab extension created, ytext.length=" + ytext.length);
      }
      return _extension;
    },
    syncPromise, // Caller can await this for sync to complete
  };
}

/**
 * Open a lightweight WebSocket subscription for a page.
 *
 * The Yjs `WebsocketProvider` opened by `createCollaborationObjects` is the
 * only place that delivers server-pushed text frames (`comments_updated`,
 * `ai_review_complete`, `links_updated`, etc.) to the browser. Pages that
 * skip Yjs collaboration (PDF pages — there is no editable text layer to
 * sync) need their own subscription so they still receive those broadcasts
 * in real time.
 *
 * Returns a cleanup function. Calling it closes the socket and stops any
 * pending reconnect.
 */
export function subscribeToPageEvents(pageExternalId) {
  if (accessDeniedPages.has(pageExternalId)) {
    return () => {};
  }

  // Derive host at call time so tests can override window.location after
  // module load. WS_HOST is captured at import time and would freeze the
  // jsdom default ("localhost:3000").
  const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${wsProtocol}//${window.location.host}/ws/pages/${pageExternalId}/`;

  let ws = null;
  let closedByCleanup = false;
  let reconnectTimer = null;
  let reconnectDelay = 1000;
  const maxDelay = 30000;
  const stopOnCloseCodes = [4001, 4003, 1008, WS_CLOSE_RATE_LIMITED];

  const open = () => {
    if (accessDeniedPages.has(pageExternalId)) return;
    try {
      ws = new WebSocket(wsUrl);
    } catch (err) {
      console.error("[subscribeToPageEvents] WS construct failed:", err);
      return;
    }
    ws.binaryType = "arraybuffer";

    ws.addEventListener("open", () => {
      reconnectDelay = 1000;
    });

    ws.addEventListener("message", (event) => {
      // Ignore Yjs binary sync frames — we never send a sync response so
      // the server's initial state vector is harmless to drop.
      if (typeof event.data !== "string") return;
      const result = dispatchPageTextEvent(pageExternalId, event.data);
      if (result === "access_denied") {
        accessDeniedPages.add(pageExternalId);
        closedByCleanup = true;
        try {
          ws.close();
        } catch {
          /* noop */
        }
      }
    });

    ws.addEventListener("close", (event) => {
      if (closedByCleanup) return;
      const code = event?.code;
      if (stopOnCloseCodes.includes(code)) {
        accessDeniedPages.add(pageExternalId);
        return;
      }
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        reconnectDelay = Math.min(reconnectDelay * 2, maxDelay);
        open();
      }, reconnectDelay);
    });

    ws.addEventListener("error", (err) => {
      console.warn("[subscribeToPageEvents] WS error:", err);
    });
  };

  open();

  return () => {
    closedByCleanup = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (ws && ws.readyState <= WebSocket.OPEN) {
      try {
        ws.close(1000, "Page closed");
      } catch {
        /* noop */
      }
    }
    ws = null;
  };
}

/**
 * Translate one server-sent text frame into a window CustomEvent.
 * Pure-ish: only side effect is the `window.dispatchEvent(...)` call.
 *
 * Returns "access_denied" when the caller should terminate the underlying
 * connection (access revoked or denied), otherwise null.
 */
function dispatchPageTextEvent(pageExternalId, raw) {
  let message;
  try {
    message = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!message || typeof message !== "object") return null;

  switch (message.type) {
    case "error":
      if (message.code === "access_denied" || message.code === "rate_limited") {
        window.dispatchEvent(
          new CustomEvent("collabError", {
            detail: { pageId: pageExternalId, code: message.code, message: message.message },
          })
        );
        return "access_denied";
      }
      return null;
    case "access_revoked":
      window.dispatchEvent(
        new CustomEvent("pageAccessRevoked", {
          detail: { pageId: pageExternalId, message: message.message },
        })
      );
      return "access_denied";
    case "links_updated":
      window.dispatchEvent(
        new CustomEvent("linksUpdated", { detail: { pageId: message.page_id } })
      );
      return null;
    case "rewind_created":
      window.dispatchEvent(
        new CustomEvent("rewindCreated", {
          detail: { pageId: message.page_id, rewind: message.rewind },
        })
      );
      return null;
    case "folders_updated":
      window.dispatchEvent(new CustomEvent("foldersUpdated"));
      return null;
    case "comments_updated":
      window.dispatchEvent(
        new CustomEvent("commentsUpdated", { detail: { pageId: pageExternalId } })
      );
      return null;
    case "ai_review_complete":
      window.dispatchEvent(
        new CustomEvent("aiReviewComplete", {
          detail: { persona: message.persona, commentCount: message.comment_count },
        })
      );
      return null;
    default:
      return null;
  }
}

/**
 * Cleanup collaboration resources.
 * Call this when closing a page.
 */
export function destroyCollaboration(collabObjects) {
  if (!collabObjects) return;

  const { provider, ydoc } = collabObjects;

  if (provider) {
    provider.destroy();
    console.log("WebSocket provider destroyed");
  }

  if (ydoc) {
    ydoc.destroy();
    console.log("Yjs document destroyed");
  }
}

/**
 * Setup a beforeunload handler to cleanly close the WebSocket.
 * This gives the server time to process pending writes.
 */
export function setupUnloadHandler(collabObjects) {
  if (!collabObjects) return () => {};

  const handler = () => {
    const { provider } = collabObjects;
    if (provider?.ws?.readyState === WebSocket.OPEN) {
      provider.ws.close(1000, "Page unloading");
    }
  };

  window.addEventListener("beforeunload", handler);
  return () => window.removeEventListener("beforeunload", handler);
}

/**
 * Clear the access denied cache for a specific page or all pages.
 * Call this if a user regains access to a previously denied page.
 */
export function clearAccessDenied(pageExternalId = null) {
  if (pageExternalId) {
    accessDeniedPages.delete(pageExternalId);
  } else {
    accessDeniedPages.clear();
  }
}

/**
 * Generate a random color for user awareness.
 */
function getRandomColor() {
  const colors = [
    "#FF6B6B",
    "#4ECDC4",
    "#45B7D1",
    "#FFA07A",
    "#98D8C8",
    "#F7DC6F",
    "#BB8FCE",
    "#85C1E2",
    "#F8B739",
    "#52B788",
  ];
  return colors[Math.floor(Math.random() * colors.length)];
}

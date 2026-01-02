/**
 * Yjs Collaboration Setup
 * Integrates Yjs CRDT with CodeMirror for real-time collaborative editing
 */
import { yCollab } from "y-codemirror.next";
import { WebsocketProvider } from "y-websocket";
import * as Y from "yjs";
import { WS_HOST } from "./config.js";

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
      syncPromise: Promise.resolve({ synced: false, ytextHasContent: false, accessDenied: true }),
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

  // Listen to provider events
  provider.on("status", ({ status }) => {
    console.log("WebSocket status:", status); // 'connecting' | 'connected' | 'disconnected'
    if (status === "connected") {
      console.timeEnd("[PERF] WebSocket connect");
      connectionAttempts = 0; // Reset on successful connection
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
    const noRetryErrors = [4003, 4001, 1008];
    if (noRetryErrors.includes(code)) {
      console.warn(
        `Access denied (code ${code}) - stopping reconnection attempts for page ${pageExternalId}`
      );
      accessDeniedPages.add(pageExternalId);
      provider.shouldConnect = false;
      provider.disconnect();
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
      resolve({ synced: true, ytextHasContent: ytext.length > 0 });
      return;
    }

    const onSync = (isSynced) => {
      console.log("Sync status:", isSynced ? "synced" : "syncing", "ytext.length=" + ytext.length);
      if (isSynced && !syncResolved) {
        syncResolved = true;
        provider.off("sync", onSync);
        resolve({ synced: true, ytextHasContent: ytext.length > 0 });
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
        resolve({ synced: false, ytextHasContent: ytext.length > 0 });
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
        _extension = yCollab(ytext, awareness, { undoManager });
        console.log("yCollab extension created, ytext.length=" + ytext.length);
      }
      return _extension;
    },
    syncPromise, // Caller can await this for sync to complete
  };
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
